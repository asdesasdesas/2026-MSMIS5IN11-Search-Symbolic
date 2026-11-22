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


# 1. Outils de test

def brute_force_cut(G, k):
    # vérité terrain : on teste toutes les combinaisons de k personnes
    # et on garde le plus grand poids coupé (réservé aux petits graphes)
    return max(cut_weight(G, c) for c in itertools.combinations(sorted(G.nodes), k))


def weighted_path():
    # petit graphe construit à la main dont on connaît tous les résultats :
    # une chaîne de 4 personnes avec des durées de contact différentes (5, 2 et 7)
    G = nx.path_graph(4)
    nx.set_edge_attributes(G, {(0, 1): 5, (1, 2): 2, (2, 3): 7}, "weight")  # on attribue un poids à chaque arête
    return G


# 2. Objectif "contacts coupés" : calcul et méthodes de sélection

def test_cut_weight_counts_each_contact_once():
    G = weighted_path()
    assert cut_weight(G, [1]) == 5 + 2  # la personne 1 coupe ses deux contacts (0-1 et 1-2)
    assert cut_weight(G, [1, 2]) == 5 + 2 + 7 # le contact (1,2) n'est compté qu'une fois
    assert cut_weight(G, [0, 3]) == 5 + 7 # deux extrémités opposées : contacts disjoints
    assert cut_weight(G, []) == 0  # personne n'est ciblé : rien n'est coupé
    assert cut_weight(G, [1], weighted=False) == 2 # sans poids, on compte simplement 2 contacts
    assert total_weight(G) == 14  # 5 + 2 + 7


def test_strength_uses_contact_durations_not_just_counts():
    G = weighted_path()
    # les nœuds 1 et 2 ont le même degré (2 contacts) mais pas la même force :
    # c'est donc bien la durée cumulée qui doit les départager
    assert select_strength(G, 1) == [2] 


# deux décorateurs empilés : le test tourne pour chaque couple (seed, k), soit 5 x 3 = 15 cas
@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("k", [1, 2, 3])

def test_ilp_edges_matches_brute_force(seed, k):
    G = synthetic_graph(n_groups=2, group_size=7, p_in=0.5, p_out=0.1, seed=seed)
    res = solve_ilp_edges(G, k)
    assert res["optimal"] # optimum prouvé par le solveur
    assert res["objective"] == brute_force_cut(G, k) # même valeur que la force brute
    assert cut_weight(G, res["selected"]) == res["objective"]# l'objectif annoncé correspond à la sélection rendue
    assert len(set(res["selected"])) == k # k personnes distinctes


@pytest.mark.parametrize("seed", range(5))
def test_greedy_edges_between_guarantee_and_optimum(seed):
    G = synthetic_graph(n_groups=3, group_size=8, p_in=0.3, p_out=0.03, seed=seed)
    for k in (2, 3, 4):
        opt = cut_weight(G, select_ilp_edges(G, k)) # valeur optimale (référence)
        greedy = cut_weight(G, select_greedy_edges(G, k))
        assert greedy <= opt  # le glouton ne peut pas dépasser l'optimum
        assert greedy >= (1 - 1 / math.e) * opt # et il respecte sa garantie des 63 %


def test_the_edge_objective_does_not_saturate_on_a_dense_graph():
    #Là où la couverture des voisinages atteint 100 % très vite, les contacts coupés continuent de croître

    G = synthetic_graph(n_groups=3, group_size=25, p_in=0.6, p_out=0.3, seed=0)

    # part du poids total coupée par la sélection optimale, pour k croissant
    cuts = [cut_weight(G, select_ilp_edges(G, k)) / total_weight(G) for k in (2, 4, 6, 8)]

    # zip(cuts, cuts[1:]) compare chaque valeur à la suivante : la suite doit être strictement croissante (pas de plateau)
    assert all(b > a for a, b in zip(cuts, cuts[1:]))
    assert cuts[-1] < 1.0  # et il reste des contacts non coupés


def test_ilp_edges_edge_cases():
    # cas limites : k = 0, graphe sans aucun contact, k trop grand
    assert select_ilp_edges(nx.path_graph(5), 0) == []
    assert len(select_ilp_edges(nx.empty_graph(6), 2)) == 2 # aucun contact : on rend quand même k personnes
    with pytest.raises(ValueError, match="k doit être"): # on attend une erreur dont le message contient ce texte
        select_ilp_edges(nx.path_graph(5), 6)# 6 personnes demandées pour 5 existantes
    with pytest.raises(ValueError, match="k doit être"):
        select_greedy_edges(nx.path_graph(5), 6)# même garde-fou pour le glouton


def test_ilp_edges_solver_without_solution_falls_back_to_greedy(monkeypatch):
    # faux résultat de solveur : aucune solution trouvée dans le temps imparti

    fake = SimpleNamespace(x=None, status=1, message="Time limit reached", fun=None)
    # le solveur est remplacé par une fonction qui renvoie toujours ce faux résultat

    # (monkeypatch remet le vrai solveur à la fin du test)
    monkeypatch.setattr(selection, "milp", lambda *a, **kw: fake)
    G = synthetic_graph(n_groups=3, group_size=10, seed=0)
    res = solve_ilp_edges(G, 4, time_limit=0.001)

    # le repli doit être signalé : fallback=True et optimal=False
    assert res["fallback"] is True and res["optimal"] is False

    # et la sélection rendue est exactement celle du glouton
    assert res["selected"] == sorted(select_greedy_edges(G, 4))


# 3. Vérificateur indépendant : objectif "cut_weight"

@pytest.fixture
def small(tmp_path):
    # fixture : prépare pour chaque test qui la demande un petit graphe (12 personnes)
    # et le relit avec le vérificateur
    G = synthetic_graph(n_groups=2, group_size=6, p_in=0.5, p_out=0.1, seed=4)
    path = tmp_path / "g.json"
    save_graph_json(G, path)

    # on renvoie ke graphe, le dictionnaire de voisins et la liste de contacts lus par le vérificateur
    return G, verifier.load_graph(path), verifier.load_edges(path)


def edge_solution(G, selected, method="ilp_edges", optimal=None, **override):
    # fabrique une "solution" au format JSON attendu par le vérificateur, avec des valeurs justes

    sol = {"method": method, "k": len(selected), "selected": sorted(selected), "objective": "cut_weight",
           "coverage": selection.coverage(G, selected), "cut_weight": cut_weight(G, selected), "optimal": optimal}
    sol.update(override)  # update remplace les champs falsifiés
    return sol


def test_verifier_cut_weight_matches_selection_code():
    # accord entre les deux implémentations indépendantes (selection.py et verifier.py)

    # sur 8 graphes et plusieurs valeurs de k
    for seed in range(8):
        G = synthetic_graph(n_groups=3, group_size=9, seed=seed)
        edges = [(u, v, d["weight"]) for u, v, d in G.edges(data=True)] 
        #on va itérer sur toutes les arêtes du graphe, en incluant les attributs, et pour chaque arrête on extrait les noeuds et le poids

        for k in (1, 3, 6):
            sel = select_greedy_edges(G, k)
            assert verifier.cut_weight_of(edges, sel) == cut_weight(G, sel)


def test_verifier_accepts_valid_edge_solutions(small):
    G, adj, edges = small
    # une solution ILP déclarée optimale, et qui l'est vraiment : aucune erreur attendue (liste vide)
    sol = edge_solution(G, select_ilp_edges(G, 2), optimal=True)
    assert verifier.check_solution(adj, sol, edges=edges) == []
    # une solution gloutonne valide l'est aussi 
    sol = edge_solution(G, select_greedy_edges(G, 2), method="greedy_edges")
    assert verifier.check_solution(adj, sol, edges=edges) == []


def test_verifier_detects_wrong_cut_weight(small):
    G, adj, edges = small
    # on annonce un poids coupé absurde : le vérificateur doit le démasquer en recalculant
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1], cut_weight=10**6), edges=edges)
    assert any("poids coupé annoncé" in e for e in errors)


def test_verifier_detects_fake_optimal_edge_solution(small):
    G, adj, edges = small
    # on cherche la PIRE paire possible (poids coupé minimal)
    worst = min(itertools.combinations(sorted(G.nodes), 2), key=lambda c: cut_weight(G, c))

    # en s'assurant qu'elle est bien strictement moins bonne que l'optimum
    assert cut_weight(G, worst) < brute_force_cut(G, 2)

    # puis on la présente comme "optimale" : la force brute du vérificateur doit détecter le mensonge
    errors = verifier.check_solution(adj, edge_solution(G, list(worst), optimal=True), edges=edges)
    assert any("optimale" in e for e in errors)


def test_verifier_needs_edges_for_cut_weight(small):
    G, adj, _ = small
    # sans passer les contacts (edges), impossible de vérifier un poids coupé : erreur explicite
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1]))
    assert any("nécessaires" in e for e in errors)


def test_verifier_rejects_unknown_objective(small):
    G, adj, edges = small
    # un objectif inconnu ("magie") doit être refusé avec un message clair
    errors = verifier.check_solution(adj, edge_solution(G, [0, 1], objective="magie"), edges=edges)
    assert any("objectif inconnu" in e for e in errors)


# 4. Pipeline complet

def test_pipeline_edge_methods(tmp_path):
    G = synthetic_graph(n_groups=3, group_size=12, seed=2)
    
    # beta est calibré pour viser un R0 de 3 ; peu de simulations (runs=20) pour que le test reste rapide
    df = run(G, [2, 4, 6], runs=20, beta=sir.beta_for_r0(G, 0.2, 3.0), gamma=0.2,
             random_draws=4, out_dir=tmp_path / "res", verbose=False)
    
    assert set(df["method"]) == set(METHODS) # toutes les méthodes sont évaluées
    assert {"cut_weight", "cut_pct"} <= set(df.columns) # <= entre ensembles : "est inclus dans" (colonnes nouvelles bien présentes)
    assert df[df["method"] == "ilp_edges"]["optimal"].all()

    # l'ILP sur les contacts est optimal pour SON objectif : personne ne coupe plus de contacts que lui
    # tableau : une ligne par k, une colonne par méthode ; 1e-9 = tolérance sur les nombres décimaux
    cut = df.pivot(index="k", columns="method", values="cut_weight")
    for method in METHODS:
        assert (cut["ilp_edges"] >= cut[method] - 1e-9).all()

    # le glouton sur les contacts respecte sa garantie des ~63 % de l'optimum
    assert (cut["greedy_edges"] >= (1 - 1 / math.e) * cut["ilp_edges"] - 1e-9).all()

    # le vérificateur indépendant relit les solutions écrites par run() : 0 solution fausse
    save_graph_json(G, tmp_path / "g.json")
    assert verifier.verify(tmp_path / "g.json", tmp_path / "res" / "solutions") == 0
    
    # le fichier de solution mentionne bien l'objectif, et EDGE_METHODS liste exactement les méthodes sur les contacts
    saved = (tmp_path / "res" / "solutions" / "ilp_edges_k4.json").read_text()
    assert '"objective": "cut_weight"' in saved and EDGE_METHODS == {"greedy_edges", "ilp_edges"}