"""Tests de non-régression de la fusion V1 + idées V2."""
import json
from itertools import combinations

import networkx as nx
import numpy as np
import pytest

from src import sir, verifier
from src.run_experiments import run
from src.selection import coverage, select_closeness, select_kcore, select_degree, solve_ilp_coverage


# on vérifie que Closeness et K-core rendent exactement k nœuds existants, sans doublons, et restent déterministes
def test_extra_centralities_respect_budget():
    G = nx.path_graph(7)
    for method in [select_closeness, select_kcore]:
        assert len(set(method(G, 3))) == 3
        assert set(method(G, 3)) <= set(G)
        assert method(G, 3) == method(G, 3)


# la méthode K-core doit fonctionner aussi sur un graphe vide ou sans aucune arête
def test_kcore_empty_and_isolates():
    assert select_kcore(nx.Graph(), 0) == []
    assert len(select_kcore(nx.empty_graph(5), 3)) == 3


# avec beta fixé, un contact plus long doit entraîner une probabilité de transmission plus élevée
def test_weighted_probabilities_monotone_in_contact_duration():
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(0, 2, weight=100)
    # prepare() convertit les données NetworkX au format utilisé par le simulateur
    p = sir.prepare(G)
    assert p.mean_weight == 50.5
    weights = p.weights[p.index[0]]
    # on applique la formule pondérée ; expm1 évite des pertes de précision numérique pour de petites valeurs
    probs = -np.expm1(-0.08 * weights / p.mean_weight)
    assert probs[1] > probs[0]
    assert np.all((0 <= probs) & (probs <= 1))


# le mode uniforme doit donner la même simulation si seule la durée des contacts change
def test_legacy_uniform_ignores_weights():
    a, b = nx.path_graph(6), nx.path_graph(6)
    nx.set_edge_attributes(a, 2, "weight")
    nx.set_edge_attributes(b, 80, "weight")
    # même graphe de structure identique, mêmes paramètres : seuls les poids diffèrent
    ea = sir.evaluate(sir.prepare(a), [], beta=0.2, n_runs=40, transmission="uniform", seed_policy="fixed")
    eb = sir.evaluate(sir.prepare(b), [], beta=0.2, n_runs=40, transmission="uniform", seed_policy="fixed")
    assert np.array_equal(ea["rates"], eb["rates"])


# une graine fixe doit reproduire exactement les taux ; immuniser le centre d’une étoile doit aussi réduire la propagation
def test_weighted_reproducible_and_effect_of_selection():
    G = nx.star_graph(5)
    nx.set_edge_attributes(G, 5, "weight")
    p = sir.prepare(G)
    a = sir.evaluate(p, [0], beta=0.4, gamma=0.3, n_runs=70, n_seeds=1,
                     base_seed=77, transmission="weighted", seed_policy="fixed")
    b = sir.evaluate(p, [0], beta=0.4, gamma=0.3, n_runs=70, n_seeds=1,
                     base_seed=77, transmission="weighted", seed_policy="fixed")
    # la référence correspond à la même expérience sans aucune personne immunisée
    reference = sir.evaluate(p, [], beta=0.4, gamma=0.3, n_runs=70, n_seeds=1,
                             base_seed=77, transmission="weighted", seed_policy="fixed")
    assert np.array_equal(a["rates"], b["rates"])
    assert a["mean"] < reference["mean"]


# un graphe sans arêtes ne peut pas atteindre une grande épidémie : le calibrage doit signaler cette impossibilité
def test_calibration_reports_unreachable_target():
    G = nx.empty_graph(15)
    out = sir.calibrate_beta_for_attack(sir.prepare(G), target=0.75,
                                        n_seeds=1, n_runs=10, iterations=3)
    assert out["reached"] is False
    assert out["attack"] == pytest.approx(1 / 15)


# les poids négatifs n’ont pas de sens pour des durées de contact ; le simulateur doit les refuser
def test_reject_nonpositive_edge_weights():
    G = nx.Graph()
    G.add_edge(1, 2, weight=-3)
    with pytest.raises(ValueError):
        sir.prepare(G)


# on vérifie que le contrôle strict détecte les champs manquants et les types incorrects
def test_verifier_strict_missing_metrics_and_invalid_k():
    G = nx.path_graph(3)
    adj = {v: set(G[v]) for v in G}
    edges = [(0, 1, 1), (1, 2, 1)]
    solution = {"selected": [1], "k": 1, "method": "degree"}
    assert verifier.check_solution(adj, solution, edges=edges, strict=False) == []
    assert "obligatoire" in " ".join(verifier.check_solution(adj, solution, edges=edges, strict=True))
    # on remplace volontairement un entier par du texte pour tester la détection d’erreur
    solution["k"] = "1"
    assert any("k invalide" in e for e in verifier.check_solution(adj, solution, edges=edges))
    solution["k"] = 1
    # on teste une sélection contenant un nombre décimal au lieu d’un identifiant entier
    solution["selected"] = [1.0]
    assert verifier.check_solution(adj, solution, edges=edges)


# sur un petit graphe, on peut comparer l’ILP à toutes les combinaisons possibles pour contrôler l’optimalité
def test_ilp_still_exact_small_graph():
    G = nx.cycle_graph(7)
    sel = solve_ilp_coverage(G, 2)
    # la force brute cherche la plus grande couverture parmi toutes les paires de nœuds
    brute = max(coverage(G, s) for s in combinations(G.nodes, 2))
    assert sel["optimal"] and coverage(G, sel["selected"]) == brute


# test de bout en bout : graphe pondéré -> plusieurs méthodes -> JSON -> vérificateur indépendant
def test_weighted_pipeline_and_strict_verification(tmp_path):
    G = nx.path_graph(6)
    for u, v in G.edges:
        G[u][v]["weight"] = (u + 1) * 3
    # tmp_path est un dossier temporaire créé par pytest, sans toucher aux vrais résultats
    out = tmp_path / "results"
    # lancement d’une petite expérience rapide sur un graphe connu
    df = run(G, ks=[2], methods=["degree", "closeness", "kcore", "greedy", "ilp", "greedy_edges"],
             runs=12, beta=0.16, gamma=0.4, n_seeds=1, random_draws=2,
             transmission="weighted", seed_policy="fixed", out_dir=out, verbose=False)
    assert len(df) == 6
    assert set(df["transmission"]) == {"weighted"}
    # on ouvre chacune des solutions produites pour contrôler le budget
    for f in (out / "solutions").glob("*.json"):
        sol = json.loads(f.read_text())
        assert len(sol["selected"]) == 2
    # on écrit le graphe au format attendu par le vérificateur strict
    from src.data import save_graph_json
    save_graph_json(G, tmp_path / "g.json")
    assert verifier.verify(tmp_path / "g.json", out / "solutions", strict=True) == 0
