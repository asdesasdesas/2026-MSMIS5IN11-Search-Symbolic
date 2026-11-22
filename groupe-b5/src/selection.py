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


# Fonction objectif : la couverture
def closed_neighborhood(G: nx.Graph, v) -> set:
    # Voisinage fermé de v : v lui-même + tous ses voisins directs.
    # On part d'un ensemble contenant v, puis on y ajoute les clés de G[v] (= ses voisins).
    return {v} | set(G[v])


def coverage(G: nx.Graph, selected) -> int:
    # Nombre de personnes couvertes par une sélection (= taille de N[S]).
    covered = set()  # personnes déjà couvertes, sans doublon grâce à l'ensemble
    for v in selected:
        # |= fait l'union : chaque personne n'est comptée qu'une seule fois,
        # même si plusieurs nœuds sélectionnés la couvrent
        covered |= closed_neighborhood(G, v)
    return len(covered)


def _check_k(G, k):
    # Garde-fou commun à toutes les méthodes : on ne peut pas choisir
    # un nombre négatif de personnes, ni plus de personnes qu'il n'y a de nœuds.
    if not 0 <= k <= G.number_of_nodes():
        raise ValueError(f"k doit être entre 0 et {G.number_of_nodes()} (reçu : {k})")


# Heuristiques simples (classements par score)
def select_random(G: nx.Graph, k: int, seed: int = 0) -> list:
    # Référence minimale : k nœuds tirés uniformément au hasard.
    _check_k(G, k)
    # sorted(...) fixe l'ordre des nœuds : avec la même graine, on obtient toujours
    # le même tirage (reproductibilité). sample() tire sans remise.
    return random.Random(seed).sample(sorted(G.nodes), k)


def _top_k(scores: dict, k: int) -> list:
    # Renvoie les k nœuds de plus haut score.
    # Clé de tri : (-score, identifiant)
    #   - le signe moins inverse l'ordre sur le score => décroissant
    #   - l'identifiant départage les égalités => résultat déterministe
    # kv[0] = nœud, kv[1] = son score.
    return [v for v, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def select_degree(G: nx.Graph, k: int) -> list:
    # Les k nœuds ayant le plus de voisins distincts (degré non pondéré).
    _check_k(G, k)
    return _top_k(dict(G.degree()), k)


def select_betweenness(G: nx.Graph, k: int) -> list:
    # Les k nœuds par lesquels passent le plus de plus courts chemins
    # (centralité d'intermédiarité) : les "ponts" du réseau.
    _check_k(G, k)
    return _top_k(nx.betweenness_centrality(G), k)


def select_pagerank(G: nx.Graph, k: int) -> list:
    # Les k nœuds au meilleur PageRank (importance d'un nœud selon l'importance de ses voisins).
    _check_k(G, k)
    # weight=None : on ignore la durée des contacts, chaque arête compte pour 1
    return _top_k(nx.pagerank(G, weight=None), k)


def select_closeness(G: nx.Graph, k: int) -> list:
    # Les k nœuds les plus "centraux" : ceux dont la distance moyenne
    # (en plus court chemin) vers tous les autres est la plus faible.
    _check_k(G, k)
    return _top_k(nx.closeness_centrality(G), k)


def select_kcore(G: nx.Graph, k: int) -> list:
    # Les k nœuds du "cœur" le plus dense du graphe, départagés par la force.
    _check_k(G, k)
    if G.number_of_nodes() == 0:
        return []
    # core_number : pour chaque nœud, le plus grand c tel qu'il appartient
    # à un sous-graphe où tous les nœuds ont au moins c voisins
    core = nx.core_number(G)
    # force = degré pondéré (somme des poids des arêtes du nœud)
    strength = dict(G.degree(weight="weight"))
    # scale > max(force) garantit force/scale < 1 : la force ne peut donc
    # jamais dépasser un écart d'une unité de core entre deux nœuds
    scale = max(strength.values(), default=0) + 1
    # score = core + force normalisée : le core domine, la force ne sert qu'à départager
    return _top_k({v: core[v] + strength[v] / scale for v in G}, k)


# Glouton sur la couverture
def select_greedy_coverage(G: nx.Graph, k: int) -> list:
    # À chaque tour, on ajoute le nœud qui couvre le plus de personnes pas encore couvertes.
    _check_k(G, k)
    covered: set = set()    # personnes déjà couvertes par les choix précédents
    selected: list = []     # sélection, dans l'ordre de choix
    chosen: set = set()     # mêmes nœuds en ensemble : test d'appartenance rapide
    for _ in range(k):
        best, best_key = None, None  # meilleur candidat du tour et sa clé de comparaison
        # ordre trié : en cas d'égalité parfaite, le plus petit identifiant gagne
        for v in sorted(G.nodes):
            if v in chosen:
                continue  # déjà pris, on ne le re-sélectionne pas
            # gain marginal : personnes que v couvrirait et qui ne le sont pas encore
            gain = len(closed_neighborhood(G, v) - covered)
            # on compare d'abord le gain, puis le degré en cas d'égalité
            key = (gain, G.degree(v))
            if best_key is None or key > best_key:
                best, best_key = v, key
        selected.append(best)
        chosen.add(best)
        # on met à jour la couverture avec le nœud retenu
        covered |= closed_neighborhood(G, best)
    return selected


# ILP exact sur la couverture
def _ilp_model(G: nx.Graph, k: int):
    # Construit les contraintes du modèle ILP de couverture.
    # Vecteur de variables, de taille 2n : [x_0..x_{n-1}, y_0..y_{n-1}]
    #   x_i = 1 si on choisit i ; y_j = 1 si j est couvert.
    nodes = sorted(G.nodes)
    n = len(nodes)
    # un nœud peut avoir n'importe quel identifiant : on le convertit en indice 0..n-1
    index = {v: i for i, v in enumerate(nodes)}

    # Matrice creuse : une ligne par personne j, 2n colonnes (x puis y)
    A = lil_matrix((n, 2 * n))

    # Contrainte de couverture, pour chaque j :  y_j - sum_{i dans N[j]} x_i <= 0
    for j in nodes:
        row = index[j]
        A[row, n + row] = 1.0              # coefficient de y_j : +1
        for i in closed_neighborhood(G, j):
            A[row, index[i]] = -1.0        # coefficient de x_i : -1 pour tout i qui peut couvrir j
    # Borne basse -inf, borne haute 0 : on impose A @ variables <= 0.
    # Ainsi y_j ne peut valoir 1 que si au moins un x_i du voisinage vaut 1.
    cover_constraint = LinearConstraint(A.tocsr(), -np.inf, 0.0)

    # Contrainte de budget : exactement k personnes choisies.
    # Vecteur [1,...,1, 0,...,0] : somme des x_i, les y_j ne comptent pas.
    budget = np.concatenate([np.ones(n), np.zeros(n)]).reshape(1, -1)
    # bornes basse = haute = k  =>  somme(x_i) = k
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
    # on refuse tout autre mode de départage que ceux qu'on sait traiter
    if tie_break not in (None, "degree"):
        raise ValueError("tie_break doit valoir None ou 'degree'")
    nodes, n, cover_constraint, budget_constraint = _ilp_model(G, k)
    # Intégralité par variable : 1 = entière (les x_i), 0 = continue (les y_j)
    integrality = np.concatenate([np.ones(n), np.zeros(n)])
    # toutes les variables sont comprises entre 0 et 1 (x binaire grâce à l'intégralité)
    bounds = Bounds(0.0, 1.0)

    def run(c, constraints):
        # Petit raccourci pour lancer le solveur avec les mêmes réglages.
        # milp MINIMISE toujours : pour maximiser f, on lui donne c = -f.
        return milp(c, constraints=constraints, integrality=integrality, bounds=bounds,
                    options={"time_limit": time_limit})

    # étape 1 : couverture maximale
    # Coût : 0 sur les x, -1 sur les y  =>  minimiser -somme(y_j) = maximiser la couverture
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
    # Les x renvoyés sont proches de 0 ou 1 (arrondis numériques) :
    # on prend les k plus grandes valeurs. kind="stable" garde un ordre déterministe.
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    out = {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0),  # 0 = optimum prouvé ; 1 = limite de temps atteinte
        "fallback": False,
        "tie_break": None,
        "status": res.message,
        "objective": int(round(-res.fun)),  # on remet le signe : res.fun est l'opposé de la couverture
        "mip_gap": getattr(res, "mip_gap", None),  # écart à la meilleure borne connue (None si absent)
    }

    # étape 2 (optionnelle) : départager les sélections de même couverture
    # Inutile si l'étape 1 n'est pas prouvée optimale : le départage n'aurait pas de sens.
    if tie_break == "degree" and out["optimal"] and k > 0:
        best = out["objective"]  # couverture maximale C* obtenue à l'étape 1
        degree = np.array([G.degree(v) for v in nodes], dtype=float)  # degré de chaque nœud
        # Contrainte supplémentaire : somme(y_j) >= C*, i.e. ne rien perdre en couverture.
        # La petite marge 1e-6 absorbe les erreurs d'arrondi du solveur.
        keep_coverage = LinearConstraint(
            np.concatenate([np.zeros(n), np.ones(n)]).reshape(1, -1), best - 1e-6, np.inf)
        # Nouveau coût : -degré sur les x, 0 sur les y
        # => minimiser -somme(degré_i * x_i) = maximiser la somme des degrés choisis
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


# EXTENSION : couper le plus de contacts (arêtes), pondérés par leur durée
def _edge_weight(data: dict, weighted: bool) -> float:
    # Poids d'une arête : sa durée si weighted=True (1 par défaut si absente),
    # sinon 1 pour toutes (on compte alors simplement le nombre de contacts).
    return data.get("weight", 1) if weighted else 1


def cut_weight(G: nx.Graph, selected, weighted: bool = True) -> float:
    """Poids total des contacts coupés : arêtes dont au moins une extrémité est ciblée.

    Une arête entre deux personnes ciblées n'est comptée qu'UNE fois.
    """
    chosen = set(selected)  # ensemble : test d'appartenance en temps constant
    # Chaque arête est parcourue une seule fois : le "or" garantit qu'une arête
    # dont les deux extrémités sont ciblées n'est pas comptée deux fois.
    return sum(_edge_weight(d, weighted) for u, v, d in G.edges(data=True)
               if u in chosen or v in chosen)


def total_weight(G: nx.Graph, weighted: bool = True) -> float:
    # Poids de tous les contacts du graphe : sert de dénominateur pour
    # exprimer la part de contacts coupés par une sélection.
    return sum(_edge_weight(d, weighted) for _, _, d in G.edges(data=True))


def select_strength(G: nx.Graph, k: int) -> list:
    """Baseline pour l'objectif sur les contacts : les k plus grandes forces (degré pondéré)."""
    _check_k(G, k)
    # force = somme des durées de tous les contacts du nœud
    return _top_k(dict(G.degree(weight="weight")), k)


def select_greedy_edges(G: nx.Graph, k: int, weighted: bool = True) -> list:
    """Glouton : on ajoute le nœud qui coupe le plus de poids de contacts pas encore coupés."""
    _check_k(G, k)
    chosen: list = []       # sélection, dans l'ordre de choix
    chosen_set: set = set()  # même chose en ensemble, pour les tests d'appartenance
    for _ in range(k):
        best, best_key = None, None
        for v in sorted(G.nodes):  # ordre trié : départage déterministe
            if v in chosen_set:
                continue
            # Le contact (v, u) est déjà coupé si u est déjà ciblé : on ne le compte pas.
            # Le gain de v = poids de ses contacts avec des personnes non encore ciblées.
            gain = sum(_edge_weight(G[v][u], weighted) for u in G[v] if u not in chosen_set)
            # d'abord le gain, puis le degré pour départager
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
    index = {v: i for i, v in enumerate(nodes)}  # nœud -> indice de colonne
    # Chaque arête devient un triplet (indice u, indice v, poids)
    edges = [(index[u], index[v], _edge_weight(d, weighted)) for u, v, d in G.edges(data=True)]
    m = len(edges)

    if m == 0:  # aucun contact : tous les choix se valent
        return {"selected": nodes[:k], "optimal": True, "fallback": False,
                "status": "graphe sans arête", "objective": 0, "mip_gap": None}

    # Vecteur de variables de taille n+m : [x_0..x_{n-1}, z_0..z_{m-1}]
    # Coût : 0 sur les x, -w_e sur les z  =>  minimiser -somme(w_e * z_e) = maximiser le poids coupé
    c = np.concatenate([np.zeros(n), -np.array([w for _, _, w in edges], dtype=float)])
    # Une ligne par arête, n+m colonnes
    A = lil_matrix((m, n + m))
    for row, (u, v, _) in enumerate(edges):
        A[row, n + row] = 1.0   # coefficient de z_e : +1
        A[row, u] = -1.0        # coefficient de x_u : -1
        A[row, v] = -1.0        # coefficient de x_v : -1
    constraints = [
        # z_e - x_u - x_v <= 0, soit z_e <= x_u + x_v :
        # un contact n'est coupé que si l'une de ses extrémités est ciblée
        LinearConstraint(A.tocsr(), -np.inf, 0.0),
        # budget : exactement k personnes ciblées (somme des x_i = k, les z_e ne comptent pas)
        LinearConstraint(np.concatenate([np.ones(n), np.zeros(m)]).reshape(1, -1), k, k),
    ]
    # Entiers pour les x, continues pour les z (cf. la docstring)
    res = milp(c, constraints=constraints,
               integrality=np.concatenate([np.ones(n), np.zeros(m)]),
               bounds=Bounds(0.0, 1.0), options={"time_limit": time_limit})
    if res.x is None:  # solveur sans solution dans le temps imparti : repli sur le glouton, signalé
        selected = select_greedy_edges(G, k, weighted)
        return {"selected": sorted(selected), "optimal": False, "fallback": True,
                "status": f"repli sur le glouton ({res.message})",
                "objective": cut_weight(G, selected, weighted), "mip_gap": None}
    # On garde les k plus grandes valeurs de x (proches de 1 après arrondi numérique)
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    return {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0),  # True si l'optimum est prouvé
        "fallback": False,
        "status": res.message,
        # on recalcule l'objectif sur la sélection finale plutôt que de se fier à res.fun
        "objective": cut_weight(G, selected, weighted),
        "mip_gap": getattr(res, "mip_gap", None),
    }


def select_ilp_edges(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    return solve_ilp_edges(G, k, time_limit)["selected"]


# Registre des méthodes (utilisé par run_experiments.py)
# Associe le nom d'une méthode (chaîne) à sa fonction : run_experiments.py
# peut ainsi appeler la bonne sélection à partir d'un simple nom.
# select_random n'y figure pas (elle prend en plus une graine)
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