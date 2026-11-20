"""Tests de la simulation SIR."""
import networkx as nx
import numpy as np
import pytest

from src import sir
from src.data import synthetic_graph
from src.selection import select_greedy_coverage, select_random


def test_everyone_vaccinated_gives_zero():
    G = nx.complete_graph(10)
    p = sir.prepare(G)
    assert sir.evaluate(p, list(G.nodes), 0.5, 0.2, n_runs=5)["mean"] == 0.0


def test_beta_zero_only_initial_cases_are_infected():
    G = nx.complete_graph(20)
    p = sir.prepare(G)
    res = sir.evaluate(p, [], beta=0.0, gamma=0.5, n_runs=10, n_seeds=3)
    assert res["mean"] == pytest.approx(3 / 20)


def test_beta_one_infects_whole_connected_graph():
    G = nx.path_graph(15)
    p = sir.prepare(G)
    assert sir.evaluate(p, [], beta=1.0, gamma=0.1, n_runs=5, n_seeds=1)["mean"] == 1.0


def test_vaccinated_node_blocks_a_path():
    G = nx.path_graph(11)                       # 0-1-2-...-10 ; on vaccine le milieu
    p = sir.prepare(G)
    res = sir.evaluate(p, [5], beta=1.0, gamma=0.1, n_runs=30, n_seeds=1)
    assert res["mean"] < 1.0                    # le milieu coupe le chemin
    assert max(res["rates"]) <= 10 / 11         # le vacciné n'est jamais infecté


def test_reproducible_with_same_seed():
    p = sir.prepare(synthetic_graph(seed=3))
    a = sir.evaluate(p, [0, 1], 0.05, 0.2, n_runs=20, base_seed=7)["rates"]
    b = sir.evaluate(p, [0, 1], 0.05, 0.2, n_runs=20, base_seed=7)["rates"]
    assert np.array_equal(a, b)


def test_good_selection_reduces_spread_more_than_random():
    G = synthetic_graph(n_groups=4, group_size=25, p_in=0.3, p_out=0.02, seed=0)
    p = sir.prepare(G)
    beta, gamma = 0.05, 0.2
    none = sir.evaluate(p, [], beta, gamma, n_runs=150)["mean"]
    greedy = sir.evaluate(p, select_greedy_coverage(G, 10), beta, gamma, n_runs=150)["mean"]
    rand = np.mean([sir.evaluate(p, select_random(G, 10, s), beta, gamma, n_runs=40)["mean"]
                    for s in range(10)])
    assert greedy < none
    assert greedy < rand


def test_invalid_parameters():
    p = sir.prepare(nx.path_graph(4))
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        sir.run_once(p, [], 0.1, 0.0, 1, rng)
    with pytest.raises(ValueError):
        sir.run_once(p, [], 1.5, 0.2, 1, rng)


def test_r0_estimate_threshold():
    G = synthetic_graph(seed=0)
    assert sir.estimate_r0(G, 0.0, 0.2) == 0.0
    assert sir.estimate_r0(G, 0.05, 0.2) > sir.estimate_r0(G, 0.02, 0.2)


@pytest.mark.parametrize("target", [1.5, 2.0, 3.0])
def test_beta_for_r0_is_consistent_with_estimate(target):
    G = synthetic_graph(n_groups=4, group_size=25, seed=1)
    beta = sir.beta_for_r0(G, gamma=0.2, r0=target)
    assert 0 < beta < 1
    assert sir.estimate_r0(G, beta, 0.2) == pytest.approx(target, rel=1e-6)


def test_beta_for_r0_impossible_target_raises():
    with pytest.raises(ValueError):
        sir.beta_for_r0(nx.path_graph(6), gamma=0.2, r0=50)
