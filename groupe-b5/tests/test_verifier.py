"""Tests du vérificateur indépendant (et recoupement avec le code de sélection)."""
import json

import pytest

from src import verifier
from src.data import save_graph_json, synthetic_graph
from src.selection import coverage, select_greedy_coverage, select_ilp_coverage


@pytest.fixture
def small(tmp_path):
    G = synthetic_graph(n_groups=2, group_size=6, p_in=0.5, p_out=0.1, seed=4)
    path = tmp_path / "g.json"
    save_graph_json(G, path)
    return G, verifier.load_graph(path), path


def solution(G, selected, method="greedy", optimal=None, **override):
    sol = {"method": method, "k": len(selected), "selected": sorted(selected),
           "coverage": coverage(G, selected), "optimal": optimal}
    sol.update(override)
    return sol


def test_verifier_coverage_matches_selection_code():
    """Deux implémentations indépendantes de la couverture doivent toujours donner le même résultat."""
    for seed in range(10):
        G = synthetic_graph(n_groups=3, group_size=9, seed=seed)
        adj = {v: set(G[v]) for v in G.nodes}
        for k in (1, 3, 6):
            sel = select_greedy_coverage(G, k)
            assert verifier.covered_count(adj, sel) == coverage(G, sel)


def test_valid_solutions_pass(small):
    G, adj, _ = small
    assert verifier.check_solution(adj, solution(G, select_greedy_coverage(G, 2))) == []
    assert verifier.check_solution(adj, solution(G, select_ilp_coverage(G, 2), "ilp", True)) == []


def test_wrong_k_detected(small):
    G, adj, _ = small
    errors = verifier.check_solution(adj, solution(G, [0, 1], k=3))
    assert any("au lieu de k=3" in e for e in errors)


def test_duplicates_detected(small):
    G, adj, _ = small
    errors = verifier.check_solution(adj, {"method": "x", "k": 2, "selected": [0, 0]})
    assert any("doublons" in e for e in errors)


def test_unknown_node_detected(small):
    _, adj, _ = small
    errors = verifier.check_solution(adj, {"method": "x", "k": 1, "selected": [999]})
    assert any("absentes du graphe" in e for e in errors)


def test_wrong_claimed_coverage_detected(small):
    G, adj, _ = small
    errors = verifier.check_solution(adj, solution(G, [0, 1], coverage=999))
    assert any("couverture annoncée" in e for e in errors)


def test_fake_optimal_claim_detected(small):
    """Une sélection volontairement mauvaise présentée comme 'optimale' doit être refusée."""
    G, adj, _ = small
    worst = min(
        (list(c) for c in __import__("itertools").combinations(G.nodes, 2)),
        key=lambda c: coverage(G, c),
    )
    best = max(coverage(G, c) for c in __import__("itertools").combinations(G.nodes, 2))
    if coverage(G, worst) < best:
        errors = verifier.check_solution(adj, solution(G, worst, "ilp", True))
        assert any("optimale" in e for e in errors)


def test_verify_folder_and_exit_code(small, tmp_path, capsys):
    G, _, graph_path = small
    folder = tmp_path / "sols"
    folder.mkdir()
    (folder / "ok.json").write_text(json.dumps(solution(G, select_greedy_coverage(G, 2))))
    (folder / "bad.json").write_text(json.dumps({"method": "x", "k": 2, "selected": [0]}))
    assert verifier.verify(graph_path, folder) == 1
    out = capsys.readouterr().out
    assert "[OK]" in out and "[ERREUR]" in out
