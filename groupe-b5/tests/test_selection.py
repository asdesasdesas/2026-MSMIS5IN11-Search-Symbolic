"""Tests des méthodes de sélection."""
import itertools
import math

import networkx as nx
import pytest

from src.data import synthetic_graph
from src.selection import (SELECTORS, coverage, select_greedy_coverage, select_ilp_coverage,
                           select_random, solve_ilp_coverage)


def brute_force(G, k):
    """Optimum par essai de toutes les combinaisons (petits graphes seulement)."""
    return max(coverage(G, c) for c in itertools.combinations(G.nodes, k))


def test_coverage_star():
    G = nx.star_graph(5)                 # centre 0, feuilles 1..5
    assert coverage(G, [0]) == 6         # le centre couvre tout le monde
    assert coverage(G, [1]) == 2         # une feuille couvre elle-même et le centre
    assert coverage(G, [1, 2]) == 3


def test_coverage_empty_selection():
    assert coverage(nx.path_graph(4), []) == 0


@pytest.mark.parametrize("method", list(SELECTORS))
def test_selection_returns_k_distinct_nodes(method):
    G = synthetic_graph(n_groups=3, group_size=10, seed=1)
    for k in (1, 3, 7):
        sel = SELECTORS[method](G, k)
        assert len(sel) == k
        assert len(set(sel)) == k
        assert set(sel) <= set(G.nodes)


def test_random_is_reproducible_and_seed_dependent():
    G = synthetic_graph(seed=2)
    assert select_random(G, 5, seed=1) == select_random(G, 5, seed=1)
    assert select_random(G, 5, seed=1) != select_random(G, 5, seed=2)


def test_k_out_of_range_raises():
    G = nx.path_graph(5)
    with pytest.raises(ValueError):
        select_greedy_coverage(G, 6)
    with pytest.raises(ValueError):
        select_ilp_coverage(G, -1)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_ilp_matches_brute_force(seed, k):
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.4, p_out=0.08, seed=seed)
    res = solve_ilp_coverage(G, k)
    assert res["optimal"]
    assert coverage(G, res["selected"]) == brute_force(G, k)
    assert res["objective"] == coverage(G, res["selected"])


@pytest.mark.parametrize("seed", range(6))
def test_greedy_between_guarantee_and_optimum(seed):
    G = synthetic_graph(n_groups=3, group_size=8, p_in=0.3, p_out=0.03, seed=seed)
    for k in (2, 3, 4):
        opt = coverage(G, select_ilp_coverage(G, k))
        greedy = coverage(G, select_greedy_coverage(G, k))
        assert greedy <= opt
        assert greedy >= (1 - 1 / math.e) * opt


def test_ilp_on_star_picks_center():
    G = nx.star_graph(8)
    assert select_ilp_coverage(G, 1) == [0]
