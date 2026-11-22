"""Tests du vérificateur indépendant (et recoupement avec le code de sélection)"""


import json
import pytest   

from src import verifier
from src.data import save_graph_json, synthetic_graph
from src.selection import coverage, select_greedy_coverage, select_ilp_coverage


# 1? Outils de test

@pytest.fixture
def small(tmp_path):
    # fixture : pour chaque test qui la demande, on prépare un petit graphe (12 personnes),
    # on l'écrit en JSON, puis on le relit avec le vérificateur (comme en usage réel)
    G = synthetic_graph(n_groups=2, group_size=6, p_in=0.5, p_out=0.1, seed=4)
    path = tmp_path / "g.json" # tmp_path est un dossier temporaire fourni par pytest, supprimé après le test
    save_graph_json(G, path)
    
    return G, verifier.load_graph(path), path
    # on renvoie le graphe networkx, le dictionnaire de voisins lu par le vérificateur, et le chemin du fichier


def solution(G, selected, method="greedy", optimal=None, **override):
    # on fabrique une solution au format JSON attendu par le vérificateur, avec des valeurs justes
    # **override permet de falsifier un champ (par exemple k=3 ou coverage=999) pour provoquer une erreur précise

    sol = {"method": method, "k": len(selected), "selected": sorted(selected),
           "coverage": coverage(G, selected), "optimal": optimal}
    sol.update(override)  # update remplace les champs falsifiés
    return sol


# 2. Accord entre les deux implémentations

def test_verifier_coverage_matches_selection_code():
    #Deux implémentations indépendantes de la couverture doivent toujours donner le même résultat

    # 10 graphes aléatoires différents, et trois valeurs de k par graphe
    for seed in range(10):
        G = synthetic_graph(n_groups=3, group_size=9, seed=seed)
        # le vérificateur travaille sur un dictionnaire {personne: ensemble de voisins}
        adj = {v: set(G[v]) for v in G.nodes} #on crée un dictionnaire qui associe chaque nœud v à l'ensemble de ses voisins.
        for k in (1, 3, 6):
            sel = select_greedy_coverage(G, k) # sel est la liste des k personnes sélectionnées par le glouton.
        #méthode déterministe  et rapide, elle prdofuit une sélection valide
            assert verifier.covered_count(adj, sel) == coverage(G, sel)
        #on compare deux implémentations différentes pour verifier qu'elles produisent le même résultat


# 3. Une solution valide est acceptée

def test_valid_solutions_pass(small):
    G, adj, _ = small  # le "_" ignore le chemin du fichier
    # liste d'erreurs vide = solution valide
    #  une solution gloutonne non optimale
    assert verifier.check_solution(adj, solution(G, select_greedy_coverage(G, 2))) == []

    #et une solution ILP déclarée optimale
    assert verifier.check_solution(adj, solution(G, select_ilp_coverage(G, 2), "ilp", True)) == []


# 4. Les erreurs sont détectées : un test par type d'erreur

def test_wrong_k_detected(small):
    G, adj, _ = small
    # 2 personnes sélectionnées, mais la solution annonce k=3
    errors = verifier.check_solution(adj, solution(G, [0, 1], k=3))
    assert any("au lieu de k=3" in e for e in errors)  # any : vrai si au moins un message d'erreur contient ce texte


def test_duplicates_detected(small):
    G, adj, _ = small
    # la même personne (0) choisie deux fois : k=2 n'est atteint qu'en apparence
    errors = verifier.check_solution(adj, {"method": "x", "k": 2, "selected": [0, 0]})
    assert any("doublons" in e for e in errors)


def test_unknown_node_detected(small):
    _, adj, _ = small
    # la personne 999 n'existe pas dans un graphe de 12 personnes
    errors = verifier.check_solution(adj, {"method": "x", "k": 1, "selected": [999]})
    assert any("absentes du graphe" in e for e in errors)


def test_wrong_claimed_coverage_detected(small):
    G, adj, _ = small
    # couverture annoncée absurde (999) : le vérificateur la recalcule et constate l'écart
    errors = verifier.check_solution(adj, solution(G, [0, 1], coverage=999))
    assert any("couverture annoncée" in e for e in errors)


def test_fake_optimal_claim_detected(small): #Une sélection volontairement mauvaise présentée comme 'optimale' doit être refusée
    G, adj, _ = small

    # on cherche la PIRE paire de personnes (couverture minimale)
    worst = min(
        (list(c) for c in __import__("itertools").combinations(G.nodes, 2)),
        # le __import__ en ligne remplace un import de itertools en tête de fichier 

        key=lambda c: coverage(G, c),
    )
    # meilleure couverture atteignable avec 2 personnes (par force brute)
    best = max(coverage(G, c) for c in __import__("itertools").combinations(G.nodes, 2))

    # le test n'a de sens que si la pire paire est vraiment moins bonne que l'optimum
    if coverage(G, worst) < best:

        # on présente cette mauvaise paire comme optimale : le vérificateur doit le détecter
        errors = verifier.check_solution(adj, solution(G, worst, "ilp", True))
        assert any("optimale" in e for e in errors)


# 5. Vérification d'un dossier entier et code de sortie

def test_verify_folder_and_exit_code(small, tmp_path, capsys): # capsys capture ce que le programme affiche à l'écran, pour pouvoir le tester
    G, _, graph_path = small
    folder = tmp_path / "sols"
    folder.mkdir()

    # une solution correcte
    (folder / "ok.json").write_text(json.dumps(solution(G, select_greedy_coverage(G, 2))))

    #et une solution fausse (k=2 annoncé, mais une seule personne listée)
    (folder / "bad.json").write_text(json.dumps({"method": "x", "k": 2, "selected": [0]}))

    # verify renvoie le nombre de solutions fausses : exactement 1 ici
    assert verifier.verify(graph_path, folder) == 1
    
    # on doit voir les deux étiquettes dans l'affichage, une par fichier
    out = capsys.readouterr().out
    assert "[OK]" in out and "[ERREUR]" in out