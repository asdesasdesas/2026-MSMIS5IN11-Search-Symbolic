"""Méthodes de sélection de k personnes à cibler (tester / vacciner / isoler).

Objectif d'optimisation (celui du sujet) : la COUVERTURE DES VOISINAGES.
Une personne j est "couverte" si elle est choisie, ou si au moins un de ses
voisins l'est. On cherche les k personnes qui couvrent le plus de monde :

    maximiser  |N[S]|   avec  S = ensemble choisi, |S| = k,  N[S] = S + voisins de S

Cette fonction est sous-modulaire (le gain d'un nœud en plus diminue quand
l'ensemble grandit), donc le glouton a une garantie : il atteint au moins
(1 - 1/e) ~ 63 % de l'optimum (Nemhauser, Wolsey, Fisher, 1978).

Méthodes :
  - random      : k personnes tirées au hasard (référence minimale)
  - degree      : les k nœuds avec le plus de contacts distincts
  - betweenness : les k nœuds avec la plus grande centralité d'intermédiarité
  - pagerank    : les k nœuds avec le meilleur PageRank
  - greedy      : glouton sur la couverture
  - ilp         : optimum exact par programmation linéaire en nombres entiers
  - ilp_deg     : comme ilp, mais parmi les sélections de couverture optimale on prend celle
                  dont la somme des degrés est maximale (corrige la dégénérescence de l'ILP)

EXTENSION : objectif sur les CONTACTS (au lieu des voisinages).
Cibler une personne (la vacciner, l'isoler) supprime tous ses contacts. On cherche donc les k
personnes qui COUPENT le plus de contacts, chacun pesé par sa durée (poids de l'arête) :

    maximiser  W(S) = somme des poids des arêtes dont au moins une extrémité est dans S

Contrairement à la couverture, W(S) ne sature pas quand le graphe est dense. Elle est aussi
sous-modulaire (même garantie du glouton : >= 1 - 1/e de l'optimum).
  - strength      : les k nœuds de plus grande force (somme des durées de leurs contacts)
  - greedy_edges  : glouton sur W(S)
  - ilp_edges     : optimum exact de W(S) par ILP
"""
from __future__ import annotations

import random

import networkx as nx
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


# ----------------------------------------------------------------------------
# Fonction objectif
# ----------------------------------------------------------------------------
def closed_neighborhood(G: nx.Graph, v) -> set:
    """N[v] = v et ses voisins."""
    return {v} | set(G[v])


def coverage(G: nx.Graph, selected) -> int:
    """Nombre de personnes couvertes par la sélection (sélectionnés + leurs voisins)."""
    covered = set()
    for v in selected:
        covered |= closed_neighborhood(G, v)
    return len(covered)


def _check_k(G, k):
    if not 0 <= k <= G.number_of_nodes():
        raise ValueError(f"k doit être entre 0 et {G.number_of_nodes()} (reçu : {k})")


# ----------------------------------------------------------------------------
# Heuristiques simples
# ----------------------------------------------------------------------------
def select_random(G: nx.Graph, k: int, seed: int = 0) -> list:
    _check_k(G, k)
    return random.Random(seed).sample(sorted(G.nodes), k)


def _top_k(scores: dict, k: int) -> list:
    """k meilleurs scores ; en cas d'égalité on prend le plus petit identifiant (déterministe)."""
    return [v for v, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def select_degree(G: nx.Graph, k: int) -> list:
    _check_k(G, k)
    return _top_k(dict(G.degree()), k)


def select_betweenness(G: nx.Graph, k: int) -> list:
    _check_k(G, k)
    return _top_k(nx.betweenness_centrality(G), k)


def select_pagerank(G: nx.Graph, k: int) -> list:
    _check_k(G, k)
    return _top_k(nx.pagerank(G, weight=None), k)


def select_closeness(G: nx.Graph, k: int) -> list:
    """Centralité de proximité (sur le graphe agrégé, non pondéré)."""
    _check_k(G, k)
    return _top_k(nx.closeness_centrality(G), k)


def select_kcore(G: nx.Graph, k: int) -> list:
    """Classement par numéro de k-core, force pondérée en départage.

    Le numéro de k-core est calculé sur le graphe simple, pas avec les durées.
    """
    _check_k(G, k)
    if G.number_of_nodes() == 0:
        return []
    core = nx.core_number(G)
    strength = dict(G.degree(weight="weight"))
    scale = max(strength.values(), default=0) + 1
    return _top_k({v: core[v] + strength[v] / scale for v in G}, k)


# ----------------------------------------------------------------------------
# Glouton
# ----------------------------------------------------------------------------
def select_greedy_coverage(G: nx.Graph, k: int) -> list:
    """A chaque étape, on ajoute le nœud qui couvre le plus de personnes pas encore couvertes."""
    _check_k(G, k)
    covered: set = set()
    selected: list = []
    chosen: set = set()
    for _ in range(k):
        best, best_key = None, None
        for v in sorted(G.nodes):
            if v in chosen:
                continue
            gain = len(closed_neighborhood(G, v) - covered)
            key = (gain, G.degree(v))  # égalité de gain : on prend le plus connecté
            if best_key is None or key > best_key:
                best, best_key = v, key
        selected.append(best)
        chosen.add(best)
        covered |= closed_neighborhood(G, best)
    return selected


# ----------------------------------------------------------------------------
# ILP exact
# ----------------------------------------------------------------------------
def _ilp_model(G: nx.Graph, k: int):
    """Contraintes communes aux deux étapes de l'ILP (voir solve_ilp_coverage)."""
    nodes = sorted(G.nodes)
    n = len(nodes)
    index = {v: i for i, v in enumerate(nodes)}

    # une contrainte par personne j : y_j - somme_{i dans N[j]} x_i <= 0
    A = lil_matrix((n, 2 * n))
    for j in nodes:
        row = index[j]
        A[row, n + row] = 1.0
        for i in closed_neighborhood(G, j):
            A[row, index[i]] = -1.0
    cover_constraint = LinearConstraint(A.tocsr(), -np.inf, 0.0)

    # exactement k personnes choisies
    budget = np.concatenate([np.ones(n), np.zeros(n)]).reshape(1, -1)
    budget_constraint = LinearConstraint(budget, k, k)
    return nodes, n, cover_constraint, budget_constraint


def solve_ilp_coverage(G: nx.Graph, k: int, time_limit: float = 60.0, tie_break=None) -> dict:
    """Résout exactement le problème de couverture avec un solveur ILP (HiGHS via scipy).

    Variables :
        x_i dans {0,1} : 1 si on choisit la personne i
        y_j dans [0,1] : 1 si la personne j est couverte (continue suffit : voir ci-dessous)
    Modèle :
        max   somme_j y_j
        s.c.  y_j <= somme_{i dans N[j]} x_i    pour tout j   (j couvert => un voisin choisi)
              somme_i x_i = k
    Comme les x_i sont entiers, le membre de droite est un entier >= 0, donc le
    solveur met y_j = 1 dès que c'est permis : pas besoin de forcer y_j binaire.

    Problème de la dégénérescence : sur un graphe dense, la couverture maximale est atteinte
    par un très grand nombre de sélections (dès que tout le monde est couvert, toutes les
    sélections se valent) et le solveur en prend une quelconque. Avec tie_break="degree",
    on résout en DEUX ÉTAPES (ordre lexicographique) :
        étape 1 : couverture maximale C*  (optimum prouvé, comme avant)
        étape 2 : parmi les sélections de couverture >= C*, maximiser la somme des degrés
    La couverture reste optimale ; seul le choix entre sélections équivalentes change.
    """
    _check_k(G, k)
    if tie_break not in (None, "degree"):
        raise ValueError("tie_break doit valoir None ou 'degree'")
    nodes, n, cover_constraint, budget_constraint = _ilp_model(G, k)
    integrality = np.concatenate([np.ones(n), np.zeros(n)])  # 1 = entier, 0 = continu
    bounds = Bounds(0.0, 1.0)

    def run(c, constraints):
        # milp MINIMISE : on passe donc l'opposé de ce qu'on veut maximiser
        return milp(c, constraints=constraints, integrality=integrality, bounds=bounds,
                    options={"time_limit": time_limit})

    # ---- étape 1 : couverture maximale ----
    res = run(np.concatenate([np.zeros(n), -np.ones(n)]), [cover_constraint, budget_constraint])
    if res.x is None:
        # Le solveur n'a rien rendu dans le temps imparti : on se replie sur le glouton
        # (qui a une garantie) et on le signale (optimal=False, fallback=True).
        selected = select_greedy_coverage(G, k)
        return {
            "selected": sorted(selected),
            "optimal": False,
            "fallback": True,
            "tie_break": None,
            "status": f"repli sur le glouton ({res.message})",
            "objective": coverage(G, selected),
            "mip_gap": None,
        }
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    out = {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0),  # 0 = optimum prouvé ; 1 = limite de temps atteinte
        "fallback": False,
        "tie_break": None,
        "status": res.message,
        "objective": int(round(-res.fun)),
        "mip_gap": getattr(res, "mip_gap", None),
    }

    # ---- étape 2 (optionnelle) : départager les sélections de même couverture ----
    if tie_break == "degree" and out["optimal"] and k > 0:
        best = out["objective"]
        degree = np.array([G.degree(v) for v in nodes], dtype=float)
        keep_coverage = LinearConstraint(
            np.concatenate([np.zeros(n), np.ones(n)]).reshape(1, -1), best - 1e-6, np.inf)
        res2 = run(np.concatenate([-degree, np.zeros(n)]),
                   [cover_constraint, budget_constraint, keep_coverage])
        if res2.x is not None and res2.status == 0:
            sel2 = [nodes[i] for i in np.argsort(-res2.x[:n], kind="stable")[:k]]
            if coverage(G, sel2) == best:      # garde-fou numérique : la couverture ne doit pas baisser
                out["selected"] = sorted(sel2)
                out["tie_break"] = "degree"
    return out


def select_ilp_coverage(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    """ILP pur : couverture maximale, sans départage (peut tomber sur une sélection quelconque)."""
    return solve_ilp_coverage(G, k, time_limit)["selected"]


def select_ilp_degree(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    """ILP en deux étapes : couverture maximale, puis somme des degrés maximale."""
    return solve_ilp_coverage(G, k, time_limit, tie_break="degree")["selected"]


# ----------------------------------------------------------------------------
# EXTENSION : couper le plus de contacts (arêtes), pondérés par leur durée
# ----------------------------------------------------------------------------
def _edge_weight(data: dict, weighted: bool) -> float:
    return data.get("weight", 1) if weighted else 1


def cut_weight(G: nx.Graph, selected, weighted: bool = True) -> float:
    """Poids total des contacts coupés : arêtes dont au moins une extrémité est ciblée.

    Une arête entre deux personnes ciblées n'est comptée qu'UNE fois.
    """
    chosen = set(selected)
    return sum(_edge_weight(d, weighted) for u, v, d in G.edges(data=True)
               if u in chosen or v in chosen)


def total_weight(G: nx.Graph, weighted: bool = True) -> float:
    return sum(_edge_weight(d, weighted) for _, _, d in G.edges(data=True))


def select_strength(G: nx.Graph, k: int) -> list:
    """Baseline pour l'objectif sur les contacts : les k plus grandes forces (degré pondéré)."""
    _check_k(G, k)
    return _top_k(dict(G.degree(weight="weight")), k)


def select_greedy_edges(G: nx.Graph, k: int, weighted: bool = True) -> list:
    """Glouton : on ajoute le nœud qui coupe le plus de poids de contacts pas encore coupés."""
    _check_k(G, k)
    chosen: list = []
    chosen_set: set = set()
    for _ in range(k):
        best, best_key = None, None
        for v in sorted(G.nodes):
            if v in chosen_set:
                continue
            # un contact (v, u) est déjà coupé si u est déjà ciblé
            gain = sum(_edge_weight(G[v][u], weighted) for u in G[v] if u not in chosen_set)
            key = (gain, G.degree(v))
            if best_key is None or key > best_key:
                best, best_key = v, key
        chosen.append(best)
        chosen_set.add(best)
    return chosen


def solve_ilp_edges(G: nx.Graph, k: int, time_limit: float = 60.0, weighted: bool = True) -> dict:
    """Optimum exact de l'objectif "contacts coupés" par ILP (HiGHS via scipy).

    Variables :
        x_i dans {0,1} : 1 si on cible la personne i
        z_e dans [0,1] : 1 si le contact e = (u, v) est coupé (continue suffit, comme pour la couverture)
    Modèle :
        max   somme_e w_e * z_e
        s.c.  z_e <= x_u + x_v     pour chaque contact e = (u, v)
              somme_i x_i = k
    """
    _check_k(G, k)
    nodes = sorted(G.nodes)
    n = len(nodes)
    index = {v: i for i, v in enumerate(nodes)}
    edges = [(index[u], index[v], _edge_weight(d, weighted)) for u, v, d in G.edges(data=True)]
    m = len(edges)

    if m == 0:  # aucun contact : tous les choix se valent
        return {"selected": nodes[:k], "optimal": True, "fallback": False,
                "status": "graphe sans arête", "objective": 0, "mip_gap": None}

    c = np.concatenate([np.zeros(n), -np.array([w for _, _, w in edges], dtype=float)])
    A = lil_matrix((m, n + m))
    for row, (u, v, _) in enumerate(edges):
        A[row, n + row] = 1.0
        A[row, u] = -1.0
        A[row, v] = -1.0
    constraints = [
        LinearConstraint(A.tocsr(), -np.inf, 0.0),
        LinearConstraint(np.concatenate([np.ones(n), np.zeros(m)]).reshape(1, -1), k, k),
    ]
    res = milp(c, constraints=constraints,
               integrality=np.concatenate([np.ones(n), np.zeros(m)]),
               bounds=Bounds(0.0, 1.0), options={"time_limit": time_limit})
    if res.x is None:  # solveur sans solution dans le temps imparti : repli sur le glouton, signalé
        selected = select_greedy_edges(G, k, weighted)
        return {"selected": sorted(selected), "optimal": False, "fallback": True,
                "status": f"repli sur le glouton ({res.message})",
                "objective": cut_weight(G, selected, weighted), "mip_gap": None}
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    return {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0),
        "fallback": False,
        "status": res.message,
        "objective": cut_weight(G, selected, weighted),
        "mip_gap": getattr(res, "mip_gap", None),
    }


def select_ilp_edges(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    return solve_ilp_edges(G, k, time_limit)["selected"]


# ----------------------------------------------------------------------------
# Registre des méthodes (utilisé par run_experiments.py)
# ----------------------------------------------------------------------------
SELECTORS = {
    "degree": select_degree,
    "betweenness": select_betweenness,
    "pagerank": select_pagerank,
    "closeness": select_closeness,
    "kcore": select_kcore,
    "greedy": select_greedy_coverage,
    "ilp": select_ilp_coverage,
    "ilp_deg": select_ilp_degree,
    "strength": select_strength,
    "greedy_edges": select_greedy_edges,
    "ilp_edges": select_ilp_edges,
}
