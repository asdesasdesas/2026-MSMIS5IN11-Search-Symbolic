"""Vérificateur INDÉPENDANT des solutions.

Indépendant = il n'importe ni networkx, ni selection.py, ni sir.py : il relit le graphe
(JSON) et la solution (JSON) et recalcule tout avec sa propre implémentation, en
bibliothèque standard uniquement. Comme ça, un bug dans le code de sélection ne peut
pas se cacher dans le vérificateur.

Ce qu'il contrôle pour chaque solution :
  1. la sélection est une liste de k personnes DISTINCTES qui existent dans le graphe ;
  2. la couverture annoncée est exacte (recalculée du point de vue de chaque personne) ;
  3. si la solution annonce un "cut_weight" (poids des contacts coupés), il est recalculé aussi ;
  4. si le graphe est assez petit, un test par force brute vérifie, pour l'objectif annoncé
     ("coverage" par défaut, ou "cut_weight" pour les méthodes sur les contacts), que
        - aucune sélection ne fait mieux que celle annoncée "optimale" (cas de l'ILP),
        - le glouton respecte sa garantie (>= 1 - 1/e de l'optimum).

Utilisation :
    python -m src.verifier --graph data/processed/hospital_graph.json \
                           --solutions results/hospital/solutions
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import combinations
from pathlib import Path


# Lecture du graphe (sans networkx)
def load_graph(path):
    """Renvoie {personne: ensemble de voisins} à partir du JSON du graphe."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # un ensemble vide de voisins par personne, y compris les personnes isolées
    adj = {int(v): set() for v in data["nodes"]}
    # `u, v, *_` : on ne garde que les deux extrémités, le reste (poids...) est ignoré ici
    for u, v, *_ in data["edges"]:
        # graphe non orienté : on enregistre la relation dans les deux sens
        adj[int(u)].add(int(v))
        adj[int(v)].add(int(u))
    return adj


def load_edges(path):
    """Renvoie la liste des contacts [(u, v, poids)] à partir du JSON du graphe."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # si une arête n'a pas de 3e élément, son poids vaut 1 par défaut
    return [(int(e[0]), int(e[1]), e[2] if len(e) > 2 else 1) for e in data["edges"]]


# Objectif "contacts coupés"
def cut_weight_of(edges, selected):
    """Poids total des contacts dont au moins une extrémité est ciblée (recalcul indépendant)."""
    chosen = set(selected)  # ensemble : test d'appartenance rapide
    # chaque arête est lue une seule fois : si ses deux extrémités sont ciblées,
    # elle n'est donc comptée qu'une fois
    return sum(w for u, v, w in edges if u in chosen or v in chosen)


def brute_force_best_cut(adj, edges, k):
    # Force brute : on teste TOUTES les façons de choisir k personnes
    # et on garde le meilleur poids coupé. Itérer sur adj donne les identifiants des personnes.
    return max(cut_weight_of(edges, c) for c in combinations(adj, k))


# Objectif "couverture"
def covered_count(adj, selected) -> int:
    """Point de vue de chaque personne : est-elle choisie, ou a-t-elle un voisin choisi ?"""
    chosen = set(selected)
    # On part de chaque personne v (et non des sélectionnés), ce qui diffère volontairement
    # de selection.py : v est couvert s'il est choisi, ou si l'intersection
    # entre ses voisins et les choisis n'est pas vide.
    return sum(1 for v, neighbours in adj.items() if v in chosen or neighbours & chosen)


def brute_force_best(adj, k) -> int:
    """Meilleure couverture possible avec k personnes (teste toutes les combinaisons)."""
    return max(covered_count(adj, c) for c in combinations(adj, k))


# Vérification d'une solution
def check_solution(adj, solution: dict, max_combinations: int = 200_000, edges=None, strict: bool = False) -> list:
    """Renvoie la liste des erreurs trouvées (liste vide = solution valide).

    `edges` (liste de (u, v, poids)) est nécessaire pour contrôler les méthodes sur les contacts.
    """
    # Une solution mal formée doit produire une erreur lisible, pas un plantage.
    if not isinstance(solution, dict):
        return ["la solution doit être un objet JSON"]
    errors = []  # on accumule toutes les erreurs au lieu de s'arrêter à la première
    selected = solution.get("selected")
    k = solution.get("k")
    objective = solution.get("objective", "coverage")  # objectif par défaut : la couverture

    # 1. format et contraintes du problème
    if not isinstance(selected, list):
        return ["'selected' doit être une liste"]  # impossible de continuer sans liste
    if objective not in ("coverage", "cut_weight"):
        errors.append(f"objectif inconnu : {objective!r}")
    # `type(k) is not int` (plutôt qu'isinstance) écarte aussi les booléens, qui sont des int en Python
    if type(k) is not int or k < 0 or k > len(adj):
        errors.append(f"k invalide : {k!r} (attendu entier entre 0 et {len(adj)})")
    elif len(selected) != k:
        errors.append(f"{len(selected)} personnes sélectionnées au lieu de k={k}")
    if any(type(v) is not int for v in selected):
        errors.append("les identifiants de personnes doivent être des entiers")
        return errors  # la suite suppose des entiers
    if len(set(selected)) != len(selected):
        errors.append("la sélection contient des doublons")
    unknown = [v for v in selected if v not in adj]
    if unknown:
        errors.append(f"personnes absentes du graphe : {unknown}")
        return errors  # inutile de continuer

    # 2. valeurs annoncées, recalculées
    real_coverage = covered_count(adj, selected)
    claimed = solution.get("coverage")
    # en mode strict, une solution doit déclarer ses métriques, sinon elle est refusée
    if strict and claimed is None:
        errors.append("champ 'coverage' obligatoire en mode strict")
    if strict and "optimal" not in solution:
        errors.append("champ 'optimal' obligatoire en mode strict")
    # une couverture annoncée doit être exactement celle qu'on recalcule
    if claimed is not None and claimed != real_coverage:
        errors.append(f"couverture annoncée {claimed} != couverture recalculée {real_coverage}")

    real_cut = None
    if edges is not None:
        real_cut = cut_weight_of(edges, selected)
        claimed_cut = solution.get("cut_weight")
        if strict and claimed_cut is None:
            errors.append("champ 'cut_weight' obligatoire en mode strict")
        # les poids peuvent être des flottants : on compare avec une petite tolérance
        if claimed_cut is not None and abs(claimed_cut - real_cut) > 1e-9:
            errors.append(f"poids coupé annoncé {claimed_cut} != poids recalculé {real_cut}")
    elif objective == "cut_weight" or "cut_weight" in solution:
        # on ne peut pas vérifier un poids coupé sans connaître les arêtes
        errors.append("les contacts du graphe sont nécessaires pour vérifier cut_weight")

    # 3. optimalité / garantie, seulement si la force brute est faisable
    # (math.comb = nombre de combinaisons à tester ; au-delà du plafond, c'est trop long)
    # et si aucune erreur précédente ne rend la comparaison sans objet
    if k is not None and not errors and math.comb(len(adj), k) <= max_combinations:
        # on compare sur l'objectif que la solution prétend optimiser
        if objective == "cut_weight":
            real, best = real_cut, brute_force_best_cut(adj, edges, k)
        else:
            real, best = real_coverage, brute_force_best(adj, k)
        name = "poids coupé" if objective == "cut_weight" else "couverture"
        # a) personne ne peut dépasser l'optimum : sinon le calcul est faux quelque part
        if real > best + 1e-9:
            errors.append(f"{name} {real} > optimum par force brute {best} (impossible)")
        # b) une solution déclarée optimale doit égaler l'optimum
        if solution.get("optimal") and abs(real - best) > 1e-9:
            errors.append(f"annoncée optimale mais {name} = {real} alors que l'optimum est {best}")
        # c) le glouton doit atteindre au moins (1 - 1/e) ~ 63 % de l'optimum
        if solution.get("method") in ("greedy", "greedy_edges") and real < (1 - 1 / math.e) * best - 1e-9:
            errors.append(f"le glouton ({real}) viole sa garantie (1-1/e)*{best}")
    return errors


def verify(graph_path, solutions_path, strict: bool = False) -> int:
    """Vérifie un fichier de solution ou tout un dossier. Renvoie le nombre de solutions fausses."""
    adj = load_graph(graph_path)
    edges = load_edges(graph_path)
    p = Path(solutions_path)
    # un dossier => tous ses .json triés (ordre d'affichage stable) ; sinon, le fichier seul
    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    if not files:
        print(f"Aucune solution trouvée dans {p}")
        return 1  # on signale un échec : rien n'a pu être vérifié
    bad = 0  # compteur de solutions invalides
    for f in files:
        try:
            errors = check_solution(adj, json.loads(f.read_text(encoding="utf-8")), edges=edges, strict=strict)
        except (ValueError, OSError) as err:       # JSON invalide, fichier illisible
            errors = [f"fichier illisible : {err}"]
        if errors:
            bad += 1
            print(f"[ERREUR] {f.name}")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"[OK]     {f.name}")
    print(f"\n{len(files) - bad}/{len(files)} solutions valides")
    return bad


def main(argv=None):
    # Interface en ligne de commande ; argv=None => lit sys.argv (utile aussi pour les tests)
    parser = argparse.ArgumentParser(description="Vérificateur indépendant des solutions")
    parser.add_argument("--graph", required=True, help="graphe au format JSON")
    parser.add_argument("--solutions", required=True, help="fichier JSON ou dossier de solutions")
    parser.add_argument("--strict", action="store_true", help="rend les métriques et l'optimalité obligatoires")
    args = parser.parse_args(argv)
    # code de sortie 1 si au moins une solution est fausse, 0 sinon (exploitable en CI)
    sys.exit(1 if verify(args.graph, args.solutions, strict=args.strict) else 0)


if __name__ == "__main__":
    main()