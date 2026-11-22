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


# 1. Données manquantes ou aberrantes
# principe commun : `match=` vérifie que le MESSAGE de l'erreur est parlant (il contient un mot-clé précis),
# pas seulement qu'une erreur quelconque est levée

def test_empty_contact_file(tmp_path):
    # fichier de contacts totalement vide : erreur explicite plutôt qu'un graphe vide muet
    f = tmp_path / "vide.dat"
    f.write_text("")
    with pytest.raises(ValueError, match="vide"):
        load_graph(f)


def test_non_integer_ids(tmp_path):
    # les identifiants de personnes doivent être des entiers ; ici "alice" et "bob" n'en sont pas
    f = tmp_path / "abc.dat"
    f.write_text("20\talice\tbob\n")
    with pytest.raises(ValueError, match="entiers"):
        load_graph(f)


def test_too_few_columns(tmp_path):
    # le format attendu est : temps, personne 1, personne 2 (3 colonnes) 
    f = tmp_path / "court.dat"
    f.write_text("20\t1\n40\t2\n")
    with pytest.raises(ValueError, match="3 colonnes"):
        load_graph(f)


def test_incomplete_lines_are_skipped_with_warning(tmp_path):
    # la 2e ligne a une colonne vide : elle est ignorée mais signalée par un avertissement et les lignes valides sont conservées
    f = tmp_path / "trous.dat"
    f.write_text("20\t1\t2\n40\t2\t\n60\t3\t4\n")
    with pytest.warns(UserWarning, match="incomplète"): # on attend un avertissement (pas une erreur)
        G = load_graph(f)
    assert sorted(G.edges) == [(1, 2), (3, 4)]


def test_corrupted_zip(tmp_path):
    # un fichier qui porte l'extension .zip mais n'en est pas un
    f = tmp_path / "casse.csv.zip"
    f.write_bytes(b"ceci n'est pas une archive zip") # write_bytes : on écrit des octets bruts
    with pytest.raises(ValueError, match="zip"):
        load_graph(f)


def test_zip_without_edges_file(tmp_path):
    # archive valide, mais sans le fichier edges.csv qu'on cherche à lire
    f = tmp_path / "sans_edges.csv.zip"
    with zipfile.ZipFile(f, "w") as z:   # "w" : on crée l'archive en écriture
        z.writestr("autre.csv", "a,b\n1,2\n")  # on y met un fichier quelconque
    with pytest.raises(ValueError, match="edges.csv"):
        load_graph(f)


def test_zip_with_unknown_node_ids(tmp_path):
    # incohérence entre les deux fichiers : edges.csv cite l'indice 9, absent de nodes.csv
    f = tmp_path / "ids.csv.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("edges.csv", "# source,target,time\n0,9,20\n") # 9 absent de nodes.csv
        z.writestr("nodes.csv", "# index,id,status\n0,101,MED\n1,102,NUR\n")
    with pytest.raises(ValueError, match="identifiants"):
        load_graph(f)


# 2. Instance infaisable ou dégénérée

# parametrize : le même test est lancé pour trois méthodes différentes,
# ce qui vérifie que toutes appliquent les mêmes règles sur k
@pytest.mark.parametrize("method", [select_degree, select_greedy_coverage, select_ilp_coverage])
def test_k_larger_than_population_is_infeasible(method):
    # 6 personnes à choisir parmi 5 : impossible, on attend une erreur claire
    with pytest.raises(ValueError, match="k doit être"):
        method(nx.path_graph(5), 6)


@pytest.mark.parametrize("method", [select_degree, select_greedy_coverage, select_ilp_coverage])
def test_k_zero_selects_nobody(method):
    # k = 0 est un cas valide : on ne cible personne, on rend une liste vide
    assert method(nx.path_graph(5), 0) == []


def test_empty_graph():
    G = nx.Graph()
    assert select_greedy_coverage(G, 0) == [] # k = 0 sur un graphe vide : valide
    with pytest.raises(ValueError):
        select_ilp_coverage(G, 1) # k = 1 pour 0 personne : infaisable
    # une simulation sur un graphe vide ne plante pas et rend un taux d'attaque nul
    assert sir.evaluate(sir.prepare(G), [], 0.1, 0.2, n_runs=3)["mean"] == 0.0


def test_graph_without_edges():
    G = nx.empty_graph(6) # que des personnes isolées
    # sans contact, chaque personne ciblée ne se couvre qu'elle-même : la couverture vaut donc k
    assert coverage(G, select_ilp_coverage(G, 2)) == 2
    assert coverage(G, select_greedy_coverage(G, 2)) == 2


def test_more_initial_cases_than_people_is_capped():
    p = sir.prepare(nx.complete_graph(4))
    # 50 cas initiaux demandés pour 4 personnes : le nombre est plafonné à 4
    # avec beta = 0 (aucune transmission), le taux d'attaque vaut exactement 1.0 (4 infectés sur 4),
    # ce qui prouve que le plafonnement a bien eu lieu
    assert sir.evaluate(p, [], beta=0.0, gamma=0.5, n_runs=3, n_seeds=50)["mean"] == 1.0


# 3. Solveur qui ne termine pas

def test_solver_without_solution_falls_back_to_greedy(monkeypatch): 
    #Si le solveur ne rend rien dans le temps imparti, on répond avec le glouton et on le dit

    # faux résultat de solveur : aucune solution trouvée avant la limite de temps
    fake = SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)

    # monkeypatch remplace le vrai solveur le temps du test, puis le remet automatiquement
    monkeypatch.setattr(selection, "milp", lambda *a, **kw: fake)
    G = synthetic_graph(n_groups=3, group_size=10, seed=0)
    res = solve_ilp_coverage(G, 4, time_limit=0.001)
    assert res["fallback"] is True # le repli est signalé
    assert res["optimal"] is False # on ne prétend pas avoir l'optimum
    assert res["selected"] == sorted(select_greedy_coverage(G, 4)) # la réponse est celle du glouton


def test_real_solver_with_tiny_time_limit_never_crashes():
    # ici, vrai solveur (pas de faux) avec une limite de temps absurde : 1 microseconde
    G = synthetic_graph(n_groups=4, group_size=30, seed=0)
    res = solve_ilp_coverage(G, 6, time_limit=1e-6)
    assert len(res["selected"]) == 6 # on obtient toujours k personnes, quoi qu'il arrive
    if not res["optimal"]: # limite atteinte : doit être signalé
        assert res["status"] # un message de statut non vide l'explique


# 4. Vérificateur face à des fichiers cassés

def test_verifier_survives_bad_files(tmp_path, capsys):
    # capsys capture ce que le programme affiche à l'écran, pour pouvoir le tester

    G = synthetic_graph(n_groups=2, group_size=5, seed=1)
    save_graph_json(G, tmp_path / "g.json")
    folder = tmp_path / "sols"
    folder.mkdir()
    (folder / "pas_du_json.json").write_text("{ceci n'est pas du json") # JSON syntaxiquement invalide
    (folder / "liste.json").write_text(json.dumps([1, 2, 3])) # JSON valide, mais ce n'est pas un objet

    # les deux fichiers sont comptés comme faux, sans que le vérificateur ne plante
    assert verifier.verify(tmp_path / "g.json", folder) == 2
    assert "illisible" in capsys.readouterr().out  # le premier est signalé comme illisible


def test_verifier_empty_folder(tmp_path):
    G = synthetic_graph(n_groups=2, group_size=5, seed=1)
    save_graph_json(G, tmp_path / "g.json")
    (tmp_path / "vide").mkdir()

    # dossier sans aucune solution : rien n'a pu être vérifié, donc c'est un échec (code 1)
    assert verifier.verify(tmp_path / "g.json", tmp_path / "vide") == 1


# 5. Réseau indisponible (téléchargement)

def _load_download_script():
    # le script de téléchargement n'est pas dans le paquet src : on le charge à la main depuis son chemin
    # (data/download_data.py, à la racine du projet, un cran au-dessus du dossier des tests)
    # pour pouvoir l'importer comme un module et l'appeler dans les tests
    path = Path(__file__).resolve().parent.parent / "data" / "download_data.py"
    spec = importlib.util.spec_from_file_location("download_data", path)# description du module à charger
    module = importlib.util.module_from_spec(spec) # création du module vide
    spec.loader.exec_module(module) # exécution du fichier dans ce module
    return module


def test_download_failure_gives_manual_instructions(tmp_path, monkeypatch, capsys):
    mod = _load_download_script()
    # on redirige le dossier de téléchargement vers le dossier temporaire :
    # le test ne touche jamais aux vraies données du projet
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)

    def no_network(*args, **kwargs):
        # simule une panne réseau : toute tentative d'ouverture d'URL échoue
        raise urllib.error.URLError("pas de réseau")

    monkeypatch.setattr(mod.urllib.request, "urlopen", no_network)
    with pytest.raises(SystemExit) as exc:   # le script quitte via sys.exit : on récupère l'exception pour lire son code
        mod.main(["hospital"])
    assert exc.value.code == 1 # code de sortie 1 : échec
    assert "à la main" in capsys.readouterr().out  # le message explique comment télécharger manuellement
    assert not list(tmp_path.glob("*.zip")) # aucun fichier partiel laissé


def test_download_unknown_dataset_name():
    mod = _load_download_script()
    # un nom de jeu de données inconnu est refusé avec le code 2 (convention des erreurs d'arguments)
    with pytest.raises(SystemExit) as exc:
        mod.main(["inconnu"])
    assert exc.value.code == 2