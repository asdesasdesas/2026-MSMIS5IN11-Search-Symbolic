"""Tests de l'extension : objectif sur les contacts coupés (pondérés par la durée)."""
import itertools
import math
from types import SimpleNamespace

import networkx as nx
import pytest

from src import selection, sir, verifier
from src.data import save_graph_json, synthetic_graph
from src.run_experiments import EDGE_METHODS, METHODS, run
from src.selection import (cut_weight, select_greedy_edges, select_ilp_edges, select_strength,
                           solve_ilp_edges, total_weight)


def brute_force_cut(G, k):
    return max(cut_weight(G, c) for c in itertools.combinations(sorted(G.nodes), k))


def weighted_path():
    G = nx.path_graph(4)                       # 0-1-2-3
    nx.set_edge_attributes(G, {(0, 1): 5, (1, 2): 2, (2, 3): 7}, "weight")
    return G


def test_cut_weight_counts_each_contact_once():
    G = weighted_path()
    assert cut_weight(G, [1]) == 5 + 2
    assert cut_weight(G, [1, 2]) == 5 + 2 + 7      # le contact (1,2) n'est compté qu'une fois
    assert cut_weight(G, [0, 3]) == 5 + 7
    assert cut_weight(G, []) == 0
    assert cut_weight(G, [1], weighted=False) == 2
    assert total_weight(G) == 14


def test_strength_uses_contact_durations_not_just_counts():
    G = weighted_path()
    assert select_strength(G, 1) == [2]            # force 9 (2 + 7), contre 7 pour le nœud 1


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_ilp_edges_matches_brute_force(seed, k):
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.5, p_out=0.1, seed=seed)
    res = solve_ilp_edges(G, k)
    assert res["optimal"]
    assert res["objective"] == brute_force_cut(G, k)
    assert cut_weight(G, res["selected"]) == res["objective"]
    assert len(set(res["selected"])) == k


@pytest.mark.parametrize("seed", range(5))
def test_greedy_edges_between_guarantee_and_optimum(seed):
    G = synthetic_graph(n_groups=3, group_size=8, p_in=0.3, p_out=0.03, seed=seed)
    for k in (2, 3, 4):
        opt = cut_weight(G, select_ilp_edges(G, k))
        greedy = cut_weight(G, select_greedy_edges(G, k))
        assert greedy <= opt
        assert greedy >= (1 - 1 / math.e) * opt


def test_the_edge_objective_does_not_saturate_on_a_dense_graph():
    """Là où la couverture des voisinages atteint 100 % très vite, les contacts coupés continuent de croître."""
    G = synthetic_graph(n_groups=3, group_size=25, p_in=0.6, p_out=0.3, seed=0)
    cuts = [cut_weight(G, select_ilp_edges(G, k)) / total_weight(G) for k in (2, 4, 6, 8)]
    assert all(b > a for a, b in zip(cuts, cuts[1:]))
    assert cuts[-1] < 1.0


def test_ilp_edges_edge_cases():
    assert select_ilp_edges(nx.path_graph(5), 0) == []
    assert len(select_ilp_edges(nx.empty_graph(6), 2)) == 2          # aucun contact
    with pytest.raises(ValueError, match="k doit être"):
        select_ilp_edges(nx.path_graph(5), 6)
    with pytest.raises(ValueError, match="k doit être"):
        select_greedy_edges(nx.path_graph(5), 6)


def test_ilp_edges_solver_without_solution_falls_back_to_greedy(monkeypatch):
    fake = SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)
    monkeypatch.setattr(selection, "milp", lambda *a, **kw: fake)
    G = synthetic_graph(n_groups=3, group_size=10, seed=0)
    res = solve_ilp_edges(G, 4, time_limit=0.001)
    assert res["fallback"] is True and res["optimal"] is False
    assert res["selected"] == sorted(select_greedy_edges(G, 4))


# ---------------- vérificateur indépendant : objectif "cut_weight" ----------------
@pytest.fixture
def small(tmp_path):
    G = synthetic_graph(n_groups=2, group_size=6, p_in=0.5, p_out=0.1, seed=4)
    path = tmp_path / "g.json"
    save_graph_json(G, path)
    return G, verifier.load_graph(path), verifier.load_edges(path)


def edge_solution(G, selected, method="ilp_edges", optimal=None, **override):
    sol = {"method": method, "k": len(selected), "selected": sorted(selected), "objective": "cut_weight",
           "coverage": selection.coverage(G, selected), "cut_weight": cut_weight(G, selected), "optimal": optimal}
    sol.update(override)
    return sol


def test_verifier_cut_weight_matches_selection_code():
    for seed in range(8):
        G = synthetic_graph(n_groups=3, group_size=9, seed=seed)
        edges = [(u, v, d["weight"]) for u, v, d in G.edges(data=True)]
        for k in (1, 3, 6):
            sel = select_greedy_edges(G, k)
            assert verifier.cut_weight_of(edges, sel) == cut_weight(G, sel)


def test_verifier_accepts_valid_edge_solutions(small):
    G, adj, edges = small
    sol = edge_solution(G, select_ilp_edges(G, 2), optimal=True)
    assert verifier.check_solution(adj, sol, edges=edges) == []
    sol = edge_solution(G, select_greedy_edges(G, 2), method="greedy_edges")
    assert verifier.check_solution(adj, sol, edges=edges) == []


def test_verifier_detects_wrong_cut_weight(small):
    G, adj, edges = small
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1], cut_weight=10**6), edges=edges)
    assert any("poids coupé annoncé" in e for e in errors)


def test_verifier_detects_fake_optimal_edge_solution(small):
    G, adj, edges = small
    worst = min(itertools.combinations(sorted(G.nodes), 2), key=lambda c: cut_weight(G, c))
    assert cut_weight(G, worst) < brute_force_cut(G, 2)
    errors = verifier.check_solution(adj, edge_solution(G, list(worst), optimal=True), edges=edges)
    assert any("optimale" in e for e in errors)


def test_verifier_needs_edges_for_cut_weight(small):
    G, adj, _ = small
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1]))
    assert any("nécessaires" in e for e in errors)


def test_verifier_rejects_unknown_objective(small):
    G, adj, edges = small
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1], objective="magie"), edges=edges)
    assert any("objectif inconnu" in e for e in errors)


# ---------------- pipeline complet ----------------
def test_pipeline_edge_methods(tmp_path):
    G = synthetic_graph(n_groups=3, group_size=12, seed=2)
    df = run(G, [2, 4, 6], runs=20, beta=sir.beta_for_r0(G, 0.2, 3.0), gamma=0.2,
             random_draws=4, out_dir=tmp_path / "res", verbose=False)
    assert set(df["method"]) == set(METHODS)
    assert {"cut_weight", "cut_pct"} <= set(df.columns)
    assert df[df["method"] == "ilp_edges"]["optimal"].all()
    # l'ILP sur les contacts est optimal pour SON objectif : personne ne coupe plus de contacts que lui
    cut = df.pivot(index="k", columns="method", values="cut_weight")
    for method in METHODS:
        assert (cut["ilp_edges"] >= cut[method] - 1e-9).all()
    assert (cut["greedy_edges"] >= (1 - 1 / math.e) * cut["ilp_edges"] - 1e-9).all()
    save_graph_json(G, tmp_path / "g.json")
    assert verifier.verify(tmp_path / "g.json", tmp_path / "res" / "solutions") == 0
    saved = (tmp_path / "res" / "solutions" / "ilp_edges_k4.json").read_text()
    assert '"objective": "cut_weight"' in saved and EDGE_METHODS == {"greedy_edges", "ilp_edges"}
