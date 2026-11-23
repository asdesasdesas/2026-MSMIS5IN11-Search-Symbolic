"""Tests des méthodes de sélection."""
import itertools
import math

import networkx as nx
import pytest

from src.data import synthetic_graph
from src.selection import (SELECTORS, coverage, select_greedy_coverage, select_ilp_coverage,
                           select_random, solve_ilp_coverage)


# la force brute énumère toutes les sélections de taille k : possible uniquement pour les petits graphes
def brute_force(G, k):
    """Optimum par essai de toutes les combinaisons (petits graphes seulement)."""
    return max(coverage(G, c) for c in itertools.combinations(G.nodes, k))


# sur un graphe en étoile, choisir le centre couvre toutes les feuilles : cas idéal pour vérifier la couverture
def test_coverage_star():
    G = nx.star_graph(5)                 # centre 0, feuilles 1..5
    assert coverage(G, [0]) == 6         # le centre couvre tout le monde
    assert coverage(G, [1]) == 2         # une feuille couvre elle-même et le centre
    assert coverage(G, [1, 2]) == 3


# une sélection vide ne doit couvrir personne
def test_coverage_empty_selection():
    assert coverage(nx.path_graph(4), []) == 0


# pytest exécutera ce test avec chacune des méthodes présentes dans SELECTORS
@pytest.mark.parametrize("method", list(SELECTORS))
# chaque méthode doit respecter le budget k, ne pas répéter un nœud et ne choisir que des nœuds existants
def test_selection_returns_k_distinct_nodes(method):
    G = synthetic_graph(n_groups=3, group_size=10, seed=1)
    for k in (1, 3, 7):
        sel = SELECTORS[method](G, k)
        assert len(sel) == k
        assert len(set(sel)) == k
        assert set(sel) <= set(G.nodes)


# la même graine doit donner la même sélection aléatoire, et une autre graine peut en donner une différente
def test_random_is_reproducible_and_seed_dependent():
    G = synthetic_graph(seed=2)
    assert select_random(G, 5, seed=1) == select_random(G, 5, seed=1)
    assert select_random(G, 5, seed=1) != select_random(G, 5, seed=2)


# on attend une erreur si k est supérieur à la population ou négatif
def test_k_out_of_range_raises():
    G = nx.path_graph(5)
    with pytest.raises(ValueError):
        select_greedy_coverage(G, 6)
    with pytest.raises(ValueError):
        select_ilp_coverage(G, -1)


# on refait le contrôle sur plusieurs graphes aléatoires différents
@pytest.mark.parametrize("seed", range(6))
# sur plusieurs budgets pour ne pas valider un seul cas particulier
@pytest.mark.parametrize("k", [1, 2, 3])
# on compare l’ILP à la force brute : les couvertures optimales doivent coïncider
def test_ilp_matches_brute_force(seed, k):
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.4, p_out=0.08, seed=seed)
    # on conserve aussi le statut optimal envoyé par le solveur
    res = solve_ilp_coverage(G, k)
    assert res["optimal"]
    assert coverage(G, res["selected"]) == brute_force(G, k)
    assert res["objective"] == coverage(G, res["selected"])


@pytest.mark.parametrize("seed", range(6))
# on vérifie que le glouton reste sous l’optimum et au-dessus de la garantie théorique 1 - 1/e
def test_greedy_between_guarantee_and_optimum(seed):
    G = synthetic_graph(n_groups=3, group_size=8, p_in=0.3, p_out=0.03, seed=seed)
    for k in (2, 3, 4):
        # l’ILP sert ici de référence optimale pour mesurer le rapport du glouton
        opt = coverage(G, select_ilp_coverage(G, k))
        greedy = coverage(G, select_greedy_coverage(G, k))
        assert greedy <= opt
        assert greedy >= (1 - 1 / math.e) * opt


# sur un graphe en étoile avec k = 1, le centre est le meilleur choix possible
def test_ilp_on_star_picks_center():
    G = nx.star_graph(8)
    assert select_ilp_coverage(G, 1) == [0]
