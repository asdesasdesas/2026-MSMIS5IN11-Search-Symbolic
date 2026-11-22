"""Méthodes de sélection de k personnes à cibler (tester / vacciner / isoler).

Objectif d'optimisation : la COUVERTURE DES VOISINAGES.
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


# 1. Fonction objectif : la couverture

def closed_neighborhood(G: nx.Graph, v) -> set:
    # le voisinage fermé de v = v lui-même + tous ses voisins directs
    # set(G[v]) : G[v] contient les voisins de v, set() les met dans un ensemble
    # {v} | ... : on crée un ensemble contenant v, puis | fait l'union avec les voisins
    return {v} | set(G[v])


def coverage(G: nx.Graph, selected) -> int:
    # nombre de personnes couvertes par la sélection (les sélectionnés + leurs voisins)
    covered = set()  # on initialise un ensemble vide : un ensemble ne garde pas les doublons
    for v in selected:
        # |= fait l'union avec l'ensemble déjà couvert : une personne couverte par
        # plusieurs sélectionnés n'est donc comptée qu'une seule fois
        covered |= closed_neighborhood(G, v)
    return len(covered)  # le nombre de personnes couvertes = la taille de l'ensemble


def _check_k(G, k):
    # vérifie que k est valide : on ne peut pas choisir un nombre négatif de personnes,
    # ni plus de personnes qu'il n'y a de nœuds dans le graphe
    if not 0 <= k <= G.number_of_nodes():
        # on lève l'erreur avec un message qui rappelle l'intervalle autorisé et la valeur reçue
        raise ValueError(f"k doit être entre 0 et {G.number_of_nodes()} (reçu : {k})")


# 2. Heuristiques simples (classements par score)

def select_random(G: nx.Graph, k: int, seed: int = 0) -> list:
    # sélectionne k nœuds au hasard (référence minimale pour comparer les autres méthodes)
    _check_k(G, k)
    
    # sorted(G.nodes) : liste triée des nœuds, pour que le tirage soit le même à chaque exécution
    # random.Random(seed) : générateur aléatoire avec une graine fixe (reproductibilité)
    # sample(..., k) : tire k éléments sans remise (pas deux fois la même personne)
    return random.Random(seed).sample(sorted(G.nodes), k)


def _top_k(scores: dict, k: int) -> list:
    # prend un dictionnaire {nœud: score} et renvoie les k nœuds de plus haut score
    # sorted(scores.items(), key=...) : trie les paires (nœud, score)
    # kv[1] = le score, donc -kv[1] trie par score décroissant (le signe moins inverse l'ordre)
    #kv[0] = le nœud : en cas d'égalité de score, on départage par identifiant croissant (résultat déterministe)
    # [:k] garde les k premiers ; la compréhension de liste ne retient que le nœud (v), pas le score (_)
    return [v for v, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def select_degree(G: nx.Graph, k: int) -> list:
    # sélectionne les k nœuds avec le plus grand degré (nombre de voisins distincts)
    _check_k(G, k)
    return _top_k(dict(G.degree()), k)  # G.degree() donne (nœud, degré) ; dict() en fait un dictionnaire


def select_betweenness(G: nx.Graph, k: int) -> list:
    # sélectionne les k nœuds avec la plus grande betweenness centrality :
    # ceux par lesquels passent le plus de plus courts chemins (les "ponts" du réseau)
    _check_k(G, k)
    return _top_k(nx.betweenness_centrality(G), k)


def select_pagerank(G: nx.Graph, k: int) -> list:
    # sélectionne les k nœuds avec le plus grand PageRank
    #un nœud est important s'il est relié à des nœuds eux-mêmes importants
    _check_k(G, k)
    # weight=None signifie qu'on ne prend pas en compte les poids des arêtes : chaque contact compte pour 1
    return _top_k(nx.pagerank(G, weight=None), k)


def select_closeness(G: nx.Graph, k: int) -> list:
    # sélectionne les k nœuds avec la plus grande closeness centrality :
    # ceux dont la distance moyenne vers tous les autres nœuds est la plus faible
    _check_k(G, k)
    return _top_k(nx.closeness_centrality(G), k)


def select_kcore(G: nx.Graph, k: int) -> list:
    # sélectionne les k nœuds du "cœur" le plus dense du graphe

    _check_k(G, k)
    if G.number_of_nodes() == 0: #si le graphe est vide, on retourne rien
        return []
    
    # core_number donne à chaque nœud son numéro de k-core : le plus grand c tel que le nœud
    # fasse partie d'un sous-graphe où chaque nœud a au moins c voisins
    core = nx.core_number(G)

    # strength = degré pondéré de la même manière que les poids 
    strength = dict(G.degree(weight="weight"))

    # max(force) + 1 est strictement plus grand que toutes les forces,
    # donc force / scale reste toujours inférieure à 1 
    scale = max(strength.values(), default=0) + 1

    # score = numéro de k-core + force normalisée (entre 0 et 1) :
    # le k-core domine, la force ne sert qu'à départager deux nœuds de même k-core
    return _top_k({v: core[v] + strength[v] / scale for v in G}, k)


# 3. Glouton sur la couverture

def select_greedy_coverage(G: nx.Graph, k: int) -> list:
    # À chaque étape, on ajoute le nœud qui couvre le plus de personnes pas encore couvertes
    _check_k(G, k)
    covered: set = set() # ensemble des personnes déjà couvertes
    selected: list = [] # liste des personnes sélectionnées, dans l'ordre de choix
    chosen: set = set() # les mêmes personnes en ensemble, pour tester vite si un nœud est déjà pris
    for _ in range(k): # on répète k fois 

        # best = meilleur nœud trouvé pendant ce tour, best_key = sa clé de comparaison
        best, best_key = None, None

        # on parcourt tous les nœuds dans l'ordre trié : en cas d'égalité parfaite, le plus petit identifiant gagne
        for v in sorted(G.nodes):
            if v in chosen:
                continue  # si on a déjà choisi ce nœud, on passe au suivant

          
            gain = len(closed_neighborhood(G, v) - covered)
            # on regarde nombre de nouvelles personnes couvertes si on ajoute v et on enlève ce qui est déjà couvert du voisinage de v

            # clé de comparaison : d'abord le gain, puis le degré pour départager
            key = (gain, G.degree(v))
            if best_key is None or key > best_key:
                best, best_key = v, key  # on met à jour le meilleur nœud
        selected.append(best) # on ajoute le meilleur nœud à la sélection
        chosen.add(best) # on le marque comme choisi
        covered |= closed_neighborhood(G, best)  # on met à jour l'ensemble des personnes couvertes
    return selected  # la liste des k personnes sélectionnées


# 4. ILP exact sur la couverture

def _ilp_model(G: nx.Graph, k: int):
    # construit les contraintes du modèle ILP de couverture

    # le vecteur des variables a une taille 2n 

    nodes = sorted(G.nodes)  # liste triée des nœuds
    n = len(nodes) 

    # un nœud peut avoir n'importe quel identifiant, on l'associe à son indice 0..n-1 (sa position dans les vecteurs)
    index = {v: i for i, v in enumerate(nodes)}

    # matrice creuse de n lignes (une contrainte par personne j) et 2n colonnes (les x puis les y)
    A = lil_matrix((n, 2 * n))

    # contrainte de couverture, pour chaque personne j 
    for j in nodes:
        row = index[j]  # numéro de la ligne de la personne j
        A[row, n + row] = 1.0  # le coefficient de y_j est 1 (les y sont dans les colonnes n à 2n-1)
        for i in closed_neighborhood(G, j):
            A[row, index[i]] = -1.0  # le coefficient de x_i est -1, pour chaque i qui peut couvrir j

    # on impose A @ variables <= 0 : borne basse -infini (pas de minimum), borne haute 0
    # (A.tocsr() convertit la matrice dans un format creux plus efficace pour le calcul)
    # donc y_j ne peut valoir 1 que si au moins un x_i de son voisinage vaut 1
    cover_constraint = LinearConstraint(A.tocsr(), -np.inf, 0.0)

    # contrainte de budget : exactement k personnes choisies
    # vecteur [1, 1, ..., 1, 0, 0, ..., 0] : n uns pour les x_i, n zéros pour les y_j
    budget = np.concatenate([np.ones(n), np.zeros(n)]).reshape(1, -1)

    # bornes basse et haute toutes deux égales à k : k <= somme(x_i) <= k, c'est-à-dire somme(x_i) = k
    budget_constraint = LinearConstraint(budget, k, k)
    return nodes, n, cover_constraint, budget_constraint  # tout ce qu'il faut pour construire le modèle


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
    if tie_break not in (None, "degree"): # on vérifie que tie_break est soit None soit 'degree' : tout autre mode est refusé
        raise ValueError("tie_break doit valoir None ou 'degree'")
    
    # on récupère les contraintes du modèle
    nodes, n, cover_constraint, budget_constraint = _ilp_model(G, k)

    # vecteur d'intégralité : 1 pour les x_i (variables entières), 0 pour les y_j (variables continues)
    integrality = np.concatenate([np.ones(n), np.zeros(n)])

    # bornes : toutes les variables sont comprises entre 0 et 1
    bounds = Bounds(0.0, 1.0)

    def run(c, constraints):
        # fonction utilitaire pour lancer le solveur avec toujours les mêmes réglages
        # milp MINIMISE toujours : pour maximiser une quantité, on lui passe donc son opposé
        return milp(c, constraints=constraints, integrality=integrality, bounds=bounds,
                    options={"time_limit": time_limit})

    # étape 1 : couverture maximale
    # coût : 0 sur les x, -1 sur les y, donc minimiser -somme(y_j) revient à maximiser la couverture
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
    
    # on récupère les k nœuds avec les plus grandes valeurs de x_i (elles sont proches de 0 ou de 1, à l'arrondi près)
    # argsort(-res.x[:n]) trie les indices par valeur décroissante ; kind="stable" garde un ordre déterministe
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    out = {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0), # 0 = optimum prouvé ; 1 = limite de temps atteinte
        "fallback": False,
        "tie_break": None,
        "status": res.message,
        "objective": int(round(-res.fun)),  # res.fun est l'opposé de la couverture : on remet le signe
        "mip_gap": getattr(res, "mip_gap", None), # écart à la meilleure borne connue sinon None 
    }

    # étape 2 : départager les sélections de même couverture
    # inutile si l'étape 1 n'est pas prouvée optimale : le départage n'aurait alors pas de sens
    if tie_break == "degree" and out["optimal"] and k > 0:
        best = out["objective"]  # couverture maximale trouvée à l'étape 1
        degree = np.array([G.degree(v) for v in nodes], dtype=float)  # vecteur des degrés de chaque nœud
        # contrainte : somme(y_j) >= best - 1e-6
        # (on garde la même couverture, avec une petite tolérance numérique pour les arrondis du solveur)
        keep_coverage = LinearConstraint(
            np.concatenate([np.zeros(n), np.ones(n)]).reshape(1, -1), best - 1e-6, np.inf)
        # on maximise somme(degree_i * x_i) en minimisant -somme(degree_i * x_i)
        res2 = run(np.concatenate([-degree, np.zeros(n)]),
                   [cover_constraint, budget_constraint, keep_coverage])
        if res2.x is not None and res2.status == 0:
            sel2 = [nodes[i] for i in np.argsort(-res2.x[:n], kind="stable")[:k]]
            if coverage(G, sel2) == best: # garde-fou numérique : la couverture ne doit pas baisser
                out["selected"] = sorted(sel2)
                out["tie_break"] = "degree"
    return out


def select_ilp_coverage(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    # ILP pur : couverture maximale, sans départage (peut tomber sur une sélection quelconque).
    return solve_ilp_coverage(G, k, time_limit)["selected"]


def select_ilp_degree(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    #ILP en deux étapes : couverture maximale, puis somme des degrés maximale
    return solve_ilp_coverage(G, k, time_limit, tie_break="degree")["selected"]


# 5. EXTENSION : couper le plus de contacts (arêtes), pondérés par leur durée

def _edge_weight(data: dict, weighted: bool) -> float:
    # retourne le poids de l'arête (sa durée) si weighted=True, sinon 1 pour toutes les arêtes
    # data.get("weight", 1) : vaut 1 par défaut si l'arête n'a pas de poids
    return data.get("weight", 1) if weighted else 1


def cut_weight(G: nx.Graph, selected, weighted: bool = True) -> float:
    #Poids total des contacts coupés : arêtes dont au moins une extrémité est ciblée.
     #Une arête entre deux personnes ciblées n'est comptée qu'UNE fois.
    
    chosen = set(selected)  # ensemble des personnes ciblées (test d'appartenance rapide)
    # G.edges(data=True) donne chaque arête (u, v, attributs) une seule fois : le "or" garantit
    # qu'une arête dont les deux extrémités sont ciblées n'est pas comptée deux fois
    return sum(_edge_weight(d, weighted) for u, v, d in G.edges(data=True)
               if u in chosen or v in chosen)


def total_weight(G: nx.Graph, weighted: bool = True) -> float:
    # somme totale des poids de toutes les arêtes du graphe
    # (sert de dénominateur pour exprimer la part de contacts coupés)
    return sum(_edge_weight(d, weighted) for _, _, d in G.edges(data=True))


def select_strength(G: nx.Graph, k: int) -> list:
    #Baseline pour l'objectif sur les contacts : les k plus grandes forces
    _check_k(G, k)
    # force = somme des poids (durées) des arêtes du nœud
    return _top_k(dict(G.degree(weight="weight")), k)


def select_greedy_edges(G: nx.Graph, k: int, weighted: bool = True) -> list:
   #Glouton : on ajoute le nœud qui coupe le plus de poids de contacts pas encore coupés
    _check_k(G, k)
    chosen: list = [] # liste des nœuds choisis, dans l'ordre
    chosen_set: set = set() # le même ensemble en set, pour tester vite l'appartenance
    for _ in range(k):
        best, best_key = None, None
        for v in sorted(G.nodes): # ordre trié : départage déterministe
            if v in chosen_set:
                continue
            # un contact (v, u) est déjà coupé si u est déjà ciblé : on ne le compte donc pas
            # gain = somme des poids des arêtes (v, u) où u n'est PAS encore ciblé
            gain = sum(_edge_weight(G[v][u], weighted) for u in G[v] if u not in chosen_set)
            # clé de comparaison : d'abord le gain, puis le degré pour départager
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
    # liste des arêtes sous forme de triplets (indice de u, indice de v, poids)
    edges = [(index[u], index[v], _edge_weight(d, weighted)) for u, v, d in G.edges(data=True)]
    m = len(edges)  # nombre d'arêtes

    if m == 0:  # aucun contact : tous les choix se valent
        return {"selected": nodes[:k], "optimal": True, "fallback": False,
                "status": "graphe sans arête", "objective": 0, "mip_gap": None}

    # le vecteur de variables a une taille n+m : [x_0 ... x_{n-1}, z_0 ... z_{m-1}]
    # coefficients de l'objectif : 0 pour les x_i, -w_e pour les z_e
    # (on minimise -somme(w_e * z_e) pour maximiser somme(w_e * z_e))
    c = np.concatenate([np.zeros(n), -np.array([w for _, _, w in edges], dtype=float)])
    # matrice creuse de m lignes (une par arête) et n+m colonnes (les x puis les z)
    A = lil_matrix((m, n + m))
    for row, (u, v, _) in enumerate(edges):
        A[row, n + row] = 1.0  # coefficient de z_e : 1
        A[row, u] = -1.0 # coefficient de x_u : -1
        A[row, v] = -1.0 # coefficient de x_v : -1
    constraints = [
        # contrainte : z_e - x_u - x_v <= 0, soit z_e <= x_u + x_v
        # (un contact n'est coupé que si l'une de ses extrémités est ciblée)
        LinearConstraint(A.tocsr(), -np.inf, 0.0),
        # contrainte de budget : somme(x_i) = k (les z_e ne comptent pas)
        LinearConstraint(np.concatenate([np.ones(n), np.zeros(m)]).reshape(1, -1), k, k),
    ]
    # entiers pour les x, continus pour les z (voir la docstring)
    res = milp(c, constraints=constraints,
               integrality=np.concatenate([np.ones(n), np.zeros(m)]),
               bounds=Bounds(0.0, 1.0), options={"time_limit": time_limit})
    if res.x is None:  # solveur sans solution dans le temps imparti : repli sur le glouton, signalé
        selected = select_greedy_edges(G, k, weighted)
        return {"selected": sorted(selected), "optimal": False, "fallback": True,
                "status": f"repli sur le glouton ({res.message})",
                "objective": cut_weight(G, selected, weighted), "mip_gap": None}
    # on garde les k nœuds avec les plus grandes valeurs de x (proches de 1 après arrondi numérique)
    selected = [nodes[i] for i in np.argsort(-res.x[:n], kind="stable")[:k]]
    return {
        "selected": sorted(selected),
        "optimal": bool(res.status == 0), # True si l'optimum est prouvé
        "fallback": False,
        "status": res.message,
        # on recalcule l'objectif sur la sélection finale plutôt que de se fier à res.fun
        "objective": cut_weight(G, selected, weighted),
        "mip_gap": getattr(res, "mip_gap", None),
    }


def select_ilp_edges(G: nx.Graph, k: int, time_limit: float = 60.0) -> list:
    return solve_ilp_edges(G, k, time_limit)["selected"]


# 6. Registre des méthodes (utilisé par run_experiments.py)
# dictionnaire qui associe chaque nom de méthode à sa fonction :
# c'est ce qui permet à run_experiments.py d'appeler la bonne fonction selon le nom de la méthode
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