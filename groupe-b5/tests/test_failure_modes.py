"""Modes d'échec demandés par le guide : données manquantes ou aberrantes, solveur qui ne termine pas,
instance infaisable, indisponibilité du réseau. Chaque cas doit produire un message clair ou un repli
signalé, jamais un plantage obscur ni un résultat silencieusement faux.
"""
import importlib.util
import json
import urllib.error
import zipfile
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest

from src import selection, sir, verifier
from src.data import load_graph, save_graph_json, synthetic_graph
from src.selection import (coverage, select_degree, select_greedy_coverage, select_ilp_coverage,
                           solve_ilp_coverage)


# ---------- données manquantes ou aberrantes ----------
def test_empty_contact_file(tmp_path):
    f = tmp_path / "vide.dat"
    f.write_text("")
    with pytest.raises(ValueError, match="vide"):
        load_graph(f)


def test_non_integer_ids(tmp_path):
    f = tmp_path / "abc.dat"
    f.write_text("20\talice\tbob\n")
    with pytest.raises(ValueError, match="entiers"):
        load_graph(f)


def test_too_few_columns(tmp_path):
    f = tmp_path / "court.dat"
    f.write_text("20\t1\n40\t2\n")
    with pytest.raises(ValueError, match="3 colonnes"):
        load_graph(f)


def test_incomplete_lines_are_skipped_with_warning(tmp_path):
    f = tmp_path / "trous.dat"
    f.write_text("20\t1\t2\n40\t2\t\n60\t3\t4\n")
    with pytest.warns(UserWarning, match="incomplète"):
        G = load_graph(f)
    assert sorted(G.edges) == [(1, 2), (3, 4)]


def test_corrupted_zip(tmp_path):
    f = tmp_path / "casse.csv.zip"
    f.write_bytes(b"ceci n'est pas une archive zip")
    with pytest.raises(ValueError, match="zip"):
        load_graph(f)


def test_zip_without_edges_file(tmp_path):
    f = tmp_path / "sans_edges.csv.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("autre.csv", "a,b\n1,2\n")
    with pytest.raises(ValueError, match="edges.csv"):
        load_graph(f)


def test_zip_with_unknown_node_ids(tmp_path):
    f = tmp_path / "ids.csv.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("edges.csv", "# source,target,time\n0,9,20\n")      # 9 absent de nodes.csv
        z.writestr("nodes.csv", "# index,id,status\n0,101,MED\n1,102,NUR\n")
    with pytest.raises(ValueError, match="identifiants"):
        load_graph(f)


# ---------- instance infaisable ou dégénérée ----------
@pytest.mark.parametrize("method", [select_degree, select_greedy_coverage, select_ilp_coverage])
def test_k_larger_than_population_is_infeasible(method):
    with pytest.raises(ValueError, match="k doit être"):
        method(nx.path_graph(5), 6)


@pytest.mark.parametrize("method", [select_degree, select_greedy_coverage, select_ilp_coverage])
def test_k_zero_selects_nobody(method):
    assert method(nx.path_graph(5), 0) == []


def test_empty_graph():
    G = nx.Graph()
    assert select_greedy_coverage(G, 0) == []
    with pytest.raises(ValueError):
        select_ilp_coverage(G, 1)
    assert sir.evaluate(sir.prepare(G), [], 0.1, 0.2, n_runs=3)["mean"] == 0.0


def test_graph_without_edges():
    G = nx.empty_graph(6)                       # que des personnes isolées
    assert coverage(G, select_ilp_coverage(G, 2)) == 2
    assert coverage(G, select_greedy_coverage(G, 2)) == 2


def test_more_initial_cases_than_people_is_capped():
    p = sir.prepare(nx.complete_graph(4))
    assert sir.evaluate(p, [], beta=0.0, gamma=0.5, n_runs=3, n_seeds=50)["mean"] == 1.0


# ---------- solveur qui ne termine pas ----------
def test_solver_without_solution_falls_back_to_greedy(monkeypatch):
    """Si le solveur ne rend rien dans le temps imparti, on répond avec le glouton et on le dit."""
    fake = SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)
    monkeypatch.setattr(selection, "milp", lambda *a, **kw: fake)
    G = synthetic_graph(n_groups=3, group_size=10, seed=0)
    res = solve_ilp_coverage(G, 4, time_limit=0.001)
    assert res["fallback"] is True
    assert res["optimal"] is False
    assert res["selected"] == sorted(select_greedy_coverage(G, 4))


def test_real_solver_with_tiny_time_limit_never_crashes():
    G = synthetic_graph(n_groups=4, group_size=30, seed=0)
    res = solve_ilp_coverage(G, 6, time_limit=1e-6)
    assert len(res["selected"]) == 6
    if not res["optimal"]:                       # limite atteinte : doit être signalé
        assert res["status"]


# ---------- vérificateur face à des fichiers cassés ----------
def test_verifier_survives_bad_files(tmp_path, capsys):
    G = synthetic_graph(n_groups=2, group_size=5, seed=1)
    save_graph_json(G, tmp_path / "g.json")
    folder = tmp_path / "sols"
    folder.mkdir()
    (folder / "pas_du_json.json").write_text("{ceci n'est pas du json")
    (folder / "liste.json").write_text(json.dumps([1, 2, 3]))
    assert verifier.verify(tmp_path / "g.json", folder) == 2
    assert "illisible" in capsys.readouterr().out


def test_verifier_empty_folder(tmp_path):
    G = synthetic_graph(n_groups=2, group_size=5, seed=1)
    save_graph_json(G, tmp_path / "g.json")
    (tmp_path / "vide").mkdir()
    assert verifier.verify(tmp_path / "g.json", tmp_path / "vide") == 1


# ---------- réseau indisponible (téléchargement) ----------
def _load_download_script():
    path = Path(__file__).resolve().parent.parent / "data" / "download_data.py"
    spec = importlib.util.spec_from_file_location("download_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_failure_gives_manual_instructions(tmp_path, monkeypatch, capsys):
    mod = _load_download_script()
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)

    def no_network(*args, **kwargs):
        raise urllib.error.URLError("pas de réseau")

    monkeypatch.setattr(mod.urllib.request, "urlopen", no_network)
    with pytest.raises(SystemExit) as exc:
        mod.main(["hospital"])
    assert exc.value.code == 1
    assert "à la main" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.zip"))          # aucun fichier partiel laissé


def test_download_unknown_dataset_name():
    mod = _load_download_script()
    with pytest.raises(SystemExit) as exc:
        mod.main(["inconnu"])
    assert exc.value.code == 2
