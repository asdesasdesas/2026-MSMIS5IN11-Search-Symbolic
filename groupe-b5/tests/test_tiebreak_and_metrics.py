"""Tests de l'ILP avec départage, des nouvelles métriques SIR et du pipeline complet"""


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


def degree_sum(G, sel): # fonction qui calcule la somme des degrés des personnes sélectionnées
    # c'est la quantité que le départage "degree" cherche à maximiser
    return sum(G.degree(v) for v in sel)


# ILP avec départage

# Deux décorateurs parametrize empilés : pytest lance le test pour chaque couple (seed, k),
# soit 5 x 2 = 10 cas, sur 10 petits graphes aléatoires différents
@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("k", [2, 3])

def test_ilp_deg_is_optimal_and_maximizes_degree_among_ties(seed, k):
    #Couverture optimale et somme des degrés maximale parmi toutes les sélections optimales
    # on crée un graphe de 14 personnes (2 groupes de 7)
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.5, p_out=0.1, seed=seed)
    
    # toutes les façons de choisir k personnes : c'est la vérité terrain du test
    combos = list(itertools.combinations(sorted(G.nodes), k))
    best_cov = max(coverage(G, c) for c in combos)  # couverture maximale possible

    # parmi les sélections qui atteignent cette couverture, la meilleure somme de degrés
    best_deg = max(degree_sum(G, c) for c in combos if coverage(G, c) == best_cov)
    res = solve_ilp_coverage(G, k, tie_break="degree")

    # le départage ne doit rien perdre en couverture
    assert coverage(G, res["selected"]) == best_cov

    # et il doit effectivement trouver la meilleure somme de degrés
    assert degree_sum(G, res["selected"]) == best_deg

    # le résultat indique que l'étape de départage a bien été appliquée
    assert res["tie_break"] == "degree"


def test_ilp_deg_on_saturated_graph():
    #Clique de 8 + pendants : plusieurs sélections couvrent tout, le départage prend les plus connectés
    G = nx.complete_graph(8)  # nœuds 0 à 7, tous reliés entre eux

    # 4 "pendants" (nœuds de degré 1) : trois accrochés au nœud 0, un accroché au nœud 1
    G.add_edges_from([(0, 100), (0, 101), (0, 102), (1, 103)])
    sel = select_ilp_degree(G, 3)
    assert coverage(G, sel) == 12  # tout le monde est couvert (8 + 4 pendants)*

    # il faut les nœuds 0 et 1 pour atteindre les pendants (degrés 10 et 8) ; la 3e personne peut être
    # n'importe quelle personne de la clique : le départage en prend une de degré 7
    assert degree_sum(G, sel) == 10 + 8 + 7 # nœud 0, nœud 1 et un nœud de la clique


def test_tie_break_must_be_known():
    # un mode de départage inconnu doit lever une erreur, pas être ignoré en silence
    with pytest.raises(ValueError):
        solve_ilp_coverage(nx.path_graph(4), 2, tie_break="inconnu")


def test_second_stage_failure_keeps_first_stage_solution(monkeypatch):
    #Si l'étape de départage ne rend rien, on garde la solution (déjà optimale) de l'étape 1

    # on garde le vrai solveur et un compteur d'appels (dictionnaire : modifiable depuis la fonction flaky)
    real_milp, calls = selection.milp, {"n": 0}

    def flaky(*args, **kwargs):
        # faux solveur : se comporte normalement, sauf au 2e appel (= l'étape de départage)
        calls["n"] += 1
        if calls["n"] == 2:
            # on simule un solveur qui n'a rien trouvé avant la limite de temps
            return SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)
        return real_milp(*args, **kwargs)

    # monkeypatch remplace selection.milp le temps du test, puis le remet automatiquement à la fin
    monkeypatch.setattr(selection, "milp", flaky)
    G = synthetic_graph(n_groups=2, group_size=8, seed=0)
    res = solve_ilp_coverage(G, 3, tie_break="degree")
    assert calls["n"] == 2  # exactement deux résolutions 

    # le départage a échoué : il n'est donc pas noté, mais l'optimalité de l'étape 1 reste valable
    assert res["tie_break"] is None and res["optimal"] is True
    assert coverage(G, res["selected"]) == res["objective"]


# métriques SIR

def test_summarize_separates_the_two_populations():
    # deux petites épidémies (4 % et 5 %) et deux grandes (80 % et 90 %) ; seuil à 20 % pour les distinguer
    out = sir.summarize([0.04, 0.05, 0.8, 0.9], major_threshold=0.2)

    # pytest.approx : comparaison de nombres décimaux avec une petite tolérance d'arrondi
    assert out["p_major"] == pytest.approx(0.5)# 2 simulations sur 4 sont "majeures"
    assert out["attack_major"] == pytest.approx(0.85) # moyenne des seules majeures 
    assert out["median"] == pytest.approx(0.425)# médiane de toutes 
    assert out["mean"] == pytest.approx(0.4475) # moyenne de toutes 


def test_summarize_without_major_outbreak():
    # aucune simulation ne dépasse le seuil : la probabilité vaut 0 et la moyenne sur
    # les épidémies majeures n'est pas définie (NaN)
    out = sir.summarize([0.01, 0.02, 0.03], major_threshold=0.2)
    assert out["p_major"] == 0.0
    assert math.isnan(out["attack_major"])  
    # on ne peut pas comparer un NaN avec ==, donc on utilise math.isnan


def test_evaluate_reports_major_outbreak_probability():
    G = nx.path_graph(15)  # chaîne de 15 personnes
    p = sir.prepare(G)     # prépare le graphe pour la simulation
    # cas extrême 1 : personne n'est ciblé, beta élevé : l'épidémie démarre à tous les coups
    assert sir.evaluate(p, [], beta=1.0, gamma=0.1, n_runs=5, n_seeds=1)["p_major"] == 1.0
    # cas extrême 2 : tout le monde est ciblé : aucune épidémie majeure n'est possible
    assert sir.evaluate(p, list(G.nodes), beta=1.0, gamma=0.1, n_runs=5)["p_major"] == 0.0


# Pipeline complet

def test_run_pipeline_end_to_end_and_verifier(tmp_path):
    #run() -> fichiers -> vérificateur indépendant
    # tmp_path : dossier temporaire fourni par pytest, supprimé après le test

    G = synthetic_graph(n_groups=3, group_size=12, seed=2)

    # beta est calibré pour viser un R0 de 3 ; peu de simulations (runs=20) pour que le test reste rapide
    df = run(G, [2, 4], runs=20, beta=sir.beta_for_r0(G, 0.2, 3.0), gamma=0.2,
             random_draws=4, out_dir=tmp_path / "res", verbose=False)
    
    # toutes les méthodes déclarées ont bien été évaluées
    assert set(df["method"]) == set(METHODS)

    # les colonnes de métriques attendues sont présentes
    for col in ("attack_median", "p_major", "attack_major", "reduction_pct", "time_s"):
        assert col in df.columns

    # les statistiques de la simulation de référence (sans intervention) sont stockées dans df.attrs
    assert set(df.attrs["baseline_stats"]) == {"mean", "std", "median", "p_major", "attack_major"}

    # on définit la probabilité entre 0et 1
    assert ((df["p_major"] >= 0) & (df["p_major"] <= 1)).all()

    # les méthodes ILP doivent avoir prouvé leur optimalité (sinon la limite de temps a été atteinte)
    ilp_rows = df[df["method"].isin(["ilp", "ilp_deg"])]
    assert ilp_rows["optimal"].all()
    # l'ILP et l'ILP avec départage ont exactement la même couverture (optimale)

    # pivot : un tableau avec une ligne par k et une colonne par méthode
    cov = df.pivot(index="k", columns="method", values="coverage")
    assert (cov["ilp"] == cov["ilp_deg"]).all()

    # on écrit le graphe en JSON, puis le vérificateur indépendant relit les solutions produites par run() :
    save_graph_json(G, tmp_path / "g.json")
    assert verifier.verify(tmp_path / "g.json", tmp_path / "res" / "solutions") == 0 
    # 0 signifie qu'aucune solution n'est fausse