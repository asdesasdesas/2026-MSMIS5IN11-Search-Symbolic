"""Vérificateur indépendany des solutions.

Ce qu'il contrôle pour chaque solution :
  1. la sélection est une liste de k personnes distinctes qui existent dans le graphe ;
  2. la couverture annoncée est exacte (recalculée du point de vue de chaque personne) ;
  3. si la solution annonce un "cut_weight" (poids des contacts coupés), il est recalculé aussi ;
  4. si le graphe est assez petit, un test par force brute vérifie, pour l'objectif annoncé
     ("coverage" par défaut, ou "cut_weight" pour les méthodes sur les contacts), que
        - aucune sélection ne fait mieux que celle annoncée "optimale" (cas de l'ILP),
        - le glouton respecte sa garantie (>= 1 - 1/e de l'optimum).

"""
from __future__ import annotations  

import argparse                       
import json                           
import math                           
import sys                             
from itertools import combinations     
from pathlib import Path               


# Lecture du graphe 

def load_graph(path): #Renvoie {personne: ensemble de voisins} à partir du JSON du graphe

    # on lit le fichier en texte (UTF-8) puis json.loads le convertit en dictionnaire Python
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # on crée un ensemble vide de voisins pour chaque personne, y compris pour les personnes isolées
    adj = {int(v): set() for v in data["nodes"]}
    # chaque arête est une liste [u, v, poids] : `u, v, *_` garde les deux extrémités
    # et ignore tout le reste (le poids, ici inutile)
    for u, v, *_ in data["edges"]:
        # graphe non orienté : on enregistre la relation dans les deux sens
        adj[int(u)].add(int(v))
        adj[int(v)].add(int(u))
    return adj


def load_edges(path): #Renvoie la liste des contacts [(u, v, poids)] à partir du JSON du graphe
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # on construit un triplet (u, v, poids) par arête ; si l'arête n'a pas de 3e élément (len(e) <= 2),
    # son poids vaut 1 par défaut
    return [(int(e[0]), int(e[1]), e[2] if len(e) > 2 else 1) for e in data["edges"]]


# Objectif "contacts coupés"

def cut_weight_of(edges, selected): #Poids total des contacts dont au moins une extrémité est ciblée 
    chosen = set(selected)  # ensemble des personnes ciblées (test d'appartenance rapide)
    # chaque arête est lue une seule fois : si ses deux extrémités sont ciblées, elle n'est donc comptée qu'une fois
    return sum(w for u, v, w in edges if u in chosen or v in chosen)


def brute_force_best_cut(adj, edges, k):
    # force brute : on teste toutes les façons de choisir k personnes et on garde le meilleur poids coupé
    return max(cut_weight_of(edges, c) for c in combinations(adj, k))


# Objectif "couverture"

def covered_count(adj, selected) -> int: #Point de vue de chaque personne : est-elle choisie, ou a-t-elle un voisin choisi ?
    chosen = set(selected)
    # on part de chaque personne v, ce qui diffère volontairement de selection.py :
    # v est couvert s'il est choisi, ou si l'intersection (&) entre ses voisins et les choisis n'est pas vide*

    # sum(1 for ...) compte le nombre de personnes pour lesquelles la condition est vraie
    return sum(1 for v, neighbours in adj.items() if v in chosen or neighbours & chosen)


def brute_force_best(adj, k) -> int: #Meilleure couverture possible avec k personnes (teste toutes les combinaisons)
    return max(covered_count(adj, c) for c in combinations(adj, k))


# Vérification d'une solution

def check_solution(adj, solution: dict, max_combinations: int = 200_000, edges=None, strict: bool = False) -> list:
    #Renvoie la liste des erreurs trouvées (liste vide = solution valide) 
    # edges` (liste de (u, v, poids)) est nécessaire pour contrôler les méthodes sur les contacts
    
    # une solution mal formée doit produire une erreur lisible, pas un plantage
    if not isinstance(solution, dict):
        return ["la solution doit être un objet JSON"]
    errors = []  # on accumule toutes les erreurs au lieu de s'arrêter à la première
    selected = solution.get("selected")  # .get renvoie None si la clé est absente, sans erreur
    k = solution.get("k")
    objective = solution.get("objective", "coverage")  # objectif par défaut : la couverture

    # on met en place le format et les contraintes du problème
    if not isinstance(selected, list): # impossible de continuer sans liste
        return ["'selected' doit être une liste"]  
    if objective not in ("coverage", "cut_weight"):
        errors.append(f"objectif inconnu : {objective!r}")

    # `type(k) is not int` écarte aussi les booléens, qui sont des int en Python
    if type(k) is not int or k < 0 or k > len(adj):
        errors.append(f"k invalide : {k!r} (attendu entier entre 0 et {len(adj)})")
    elif len(selected) != k:
        errors.append(f"{len(selected)} personnes sélectionnées au lieu de k={k}")
    if any(type(v) is not int for v in selected):
        errors.append("les identifiants de personnes doivent être des entiers")
        return errors  # la suite suppose des entiers
    if len(set(selected)) != len(selected):  # un ensemble supprime les doublons : si sa taille change, il y en avait
        errors.append("la sélection contient des doublons")
    unknown = [v for v in selected if v not in adj]  # personnes qui n'existent pas dans le graphe
    if unknown:
        errors.append(f"personnes absentes du graphe : {unknown}")
        return errors  # inutile de continuer

    # valeurs annoncées, recalculées
    real_coverage = covered_count(adj, selected)
    claimed = solution.get("coverage")
    # en mode strict, une solution doit déclarer ses métriques, sinon elle est refusée
    if strict and claimed is None:
        errors.append("champ 'coverage' obligatoire en mode strict")
    if strict and "optimal" not in solution:
        errors.append("champ 'optimal' obligatoire en mode strict")
    
    if claimed is not None and claimed != real_coverage: 
        #on ne fait la vérification que si le champ existe et on vérifie que les deux valeurs sont identiques
        
        errors.append(f"couverture annoncée {claimed} != couverture recalculée {real_coverage}")
        # une couverture annoncée doit être exactement celle qu'on recalcule     
    
    real_cut = None
    if edges is not None: #vérification
        real_cut = cut_weight_of(edges, selected) #on recalcule le poids total des contacts coupés par la sélection
        claimed_cut = solution.get("cut_weight")
        if strict and claimed_cut is None:
            errors.append("champ 'cut_weight' obligatoire en mode strict")

        #comme les poids peuvent être des flottants, alors on compare avec une petite tolérance (1e-9) plutôt qu'avec ==
        if claimed_cut is not None and abs(claimed_cut - real_cut) > 1e-9:
            errors.append(f"poids coupé annoncé {claimed_cut} != poids recalculé {real_cut}")
    elif objective == "cut_weight" or "cut_weight" in solution:
        # on ne peut pas vérifier un poids coupé sans connaître les arêtes
        errors.append("les contacts du graphe sont nécessaires pour vérifier cut_weight")

    # optimalité / garantie, seulement si la force brute est faisable
    # math.comb(n, k) = nombre de combinaisons à tester ; au-delà du plafond, ce serait trop long
    # et on ne compare que si aucune erreur précédente ne rend la comparaison sans objet
    if k is not None and not errors and math.comb(len(adj), k) <= max_combinations:
        # on compare sur l'objectif que la solution prétend optimiser
        if objective == "cut_weight":
            real, best = real_cut, brute_force_best_cut(adj, edges, k)
        else:
            real, best = real_coverage, brute_force_best(adj, k)
        name = "poids coupé" if objective == "cut_weight" else "couverture"
    
        if real > best + 1e-9:    # personne ne peut dépasser l'optimum : sinon le calcul est faux quelque part
            errors.append(f"{name} {real} > optimum par force brute {best} (impossible)")
        
        if solution.get("optimal") and abs(real - best) > 1e-9:# une solution déclarée optimale doit égaler l'optimum
            errors.append(f"annoncée optimale mais {name} = {real} alors que l'optimum est {best}")

        if solution.get("method") in ("greedy", "greedy_edges") and real < (1 - 1 / math.e) * best - 1e-9:
             # le glouton doit atteindre au moins (1 - 1/e) ~ 63 % de l'optimum (math.e = le nombre e)
            errors.append(f"le glouton ({real}) viole sa garantie (1-1/e)*{best}")
    return errors


def verify(graph_path, solutions_path, strict: bool = False) -> int: #Vérifie un fichier de solution ou tout un dossier 
    adj = load_graph(graph_path)    # voisins de chaque personne
    edges = load_edges(graph_path)  # liste des contacts avec leur poids
    p = Path(solutions_path)
    # si c'est un dossier : tous ses fichiers .json, triés 
    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    if not files: #sinon, le fichier seul
        print(f"Aucune solution trouvée dans {p}")
        return 1  # on signale un échec : rien n'a pu être vérifié
    bad = 0  # compteur de solutions invalides
    for f in files: #on parcours les files qui contient tous les chemins vers les fichiers JSON de solutions 
        try:
            errors = check_solution(adj, json.loads(f.read_text(encoding="utf-8")), edges=edges, strict=strict)
            #on commence par lire le contenu du fichier f sous format chaine de caractère convertit en dictionnaire Python
            #puis on vérifie la solution et récupère la liste des erreurs avec un boléen qui indique si on est en mode de vérification strict ou non

        except (ValueError, OSError) as err:       # JSON invalide, fichier illisible
            errors = [f"fichier illisible : {err}"]
        if errors: #on fait une liste d'erreur avec les différents fichiers qui lui sont associés
            bad += 1
            print(f"[ERREUR] {f.name}")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"[OK]     {f.name}")
    print(f"\n{len(files) - bad}/{len(files)} solutions valides")
    return bad #renvoie le nombre de solutions fausses


def main(argv=None):
    # interface en ligne de commande ; argv=None signifie que l'on lit les arguments réels (sys.argv)
    parser = argparse.ArgumentParser(description="Vérificateur indépendant des solutions")
    parser.add_argument("--graph", required=True, help="graphe au format JSON")
    parser.add_argument("--solutions", required=True, help="fichier JSON ou dossier de solutions")
    # action="store_true" : l'option vaut True si elle est présente, False sinon (pas de valeur à donner)
    parser.add_argument("--strict", action="store_true", help="rend les métriques et l'optimalité obligatoires")
    args = parser.parse_args(argv)
    # code de sortie 1 si au moins une solution est fausse, 0 sinon (utile pour l'intégration continue)
    sys.exit(1 if verify(args.graph, args.solutions, strict=args.strict) else 0)


if __name__ == "__main__":  # exécuté seulement si on lance ce fichier directement (pas quand il est importé)
    main()