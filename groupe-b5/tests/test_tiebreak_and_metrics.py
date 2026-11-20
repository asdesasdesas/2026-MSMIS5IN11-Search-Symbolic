"""Tests de l'ILP avec départage, des nouvelles métriques SIR et du pipeline complet."""
import itertools
import math
from types import SimpleNamespace

import networkx as nx
import numpy as np
import pytest

from src import selection, sir, verifier
from src.data import save_graph_json, synthetic_graph
from src.run_experiments import METHODS, run
from src.selection import coverage, select_ilp_degree, solve_ilp_coverage


def degree_sum(G, sel):
    return sum(G.degree(v) for v in sel)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("k", [2, 3])
def test_ilp_deg_is_optimal_and_maximizes_degree_among_ties(seed, k):
    """Couverture optimale ET somme des degrés maximale parmi toutes les sélections optimales."""
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.5, p_out=0.1, seed=seed)
    combos = list(itertools.combinations(sorted(G.nodes), k))
    best_cov = max(coverage(G, c) for c in combos)
    best_deg = max(degree_sum(G, c) for c in combos if coverage(G, c) == best_cov)
    res = solve_ilp_coverage(G, k, tie_break="degree")
    assert coverage(G, res["selected"]) == best_cov
    assert degree_sum(G, res["selected"]) == best_deg
    assert res["tie_break"] == "degree"


def test_ilp_deg_on_saturated_graph():
    """Clique de 8 + pendants : plusieurs sélections couvrent tout, le départage prend les plus connectés."""
    G = nx.complete_graph(8)
    G.add_edges_from([(0, 100), (0, 101), (0, 102), (1, 103)])
    sel = select_ilp_degree(G, 3)
    assert coverage(G, sel) == 12                  # tout le monde est couvert
    assert degree_sum(G, sel) == 10 + 8 + 7        # nœud 0, nœud 1 et un nœud de la clique


def test_tie_break_must_be_known():
    with pytest.raises(ValueError):
        solve_ilp_coverage(nx.path_graph(4), 2, tie_break="inconnu")


def test_second_stage_failure_keeps_first_stage_solution(monkeypatch):
    """Si l'étape de départage ne rend rien, on garde la solution (déjà optimale) de l'étape 1."""
    real_milp, calls = selection.milp, {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            return SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)
        return real_milp(*args, **kwargs)

    monkeypatch.setattr(selection, "milp", flaky)
    G = synthetic_graph(n_groups=2, group_size=8, seed=0)
    res = solve_ilp_coverage(G, 3, tie_break="degree")
    assert calls["n"] == 2
    assert res["tie_break"] is None and res["optimal"] is True
    assert coverage(G, res["selected"]) == res["objective"]


def test_summarize_separates_the_two_populations():
    out = sir.summarize([0.04, 0.05, 0.8, 0.9], major_threshold=0.2)
    assert out["p_major"] == pytest.approx(0.5)
    assert out["attack_major"] == pytest.approx(0.85)
    assert out["median"] == pytest.approx(0.425)
    assert out["mean"] == pytest.approx(0.4475)


def test_summarize_without_major_outbreak():
    out = sir.summarize([0.01, 0.02, 0.03], major_threshold=0.2)
    assert out["p_major"] == 0.0
    assert math.isnan(out["attack_major"])


def test_evaluate_reports_major_outbreak_probability():
    G = nx.path_graph(15)
    p = sir.prepare(G)
    assert sir.evaluate(p, [], beta=1.0, gamma=0.1, n_runs=5, n_seeds=1)["p_major"] == 1.0
    assert sir.evaluate(p, list(G.nodes), beta=1.0, gamma=0.1, n_runs=5)["p_major"] == 0.0


def test_run_pipeline_end_to_end_and_verifier(tmp_path):
    """run() -> fichiers -> vérificateur indépendant : tout doit être cohérent."""
    G = synthetic_graph(n_groups=3, group_size=12, seed=2)
    df = run(G, [2, 4], runs=20, beta=sir.beta_for_r0(G, 0.2, 3.0), gamma=0.2,
             random_draws=4, out_dir=tmp_path / "res", verbose=False)
    assert set(df["method"]) == set(METHODS)
    for col in ("attack_median", "p_major", "attack_major", "reduction_pct", "time_s"):
        assert col in df.columns
    assert set(df.attrs["baseline_stats"]) == {"mean", "std", "median", "p_major", "attack_major"}
    assert ((df["p_major"] >= 0) & (df["p_major"] <= 1)).all()
    ilp_rows = df[df["method"].isin(["ilp", "ilp_deg"])]
    assert ilp_rows["optimal"].all()
    # l'ILP et l'ILP avec départage ont exactement la même couverture (optimale)
    cov = df.pivot(index="k", columns="method", values="coverage")
    assert (cov["ilp"] == cov["ilp_deg"]).all()
    save_graph_json(G, tmp_path / "g.json")
    assert verifier.verify(tmp_path / "g.json", tmp_path / "res" / "solutions") == 0
