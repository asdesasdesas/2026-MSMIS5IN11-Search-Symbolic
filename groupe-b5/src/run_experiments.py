"""Lance toutes les méthodes pour plusieurs valeurs de k et compare qualité / temps.

Exemples :
    # avec les vraies données (voir README, section "Données")
    python -m src.run_experiments --input data/raw/hospital.csv.zip --name hospital \
        --k 2 4 6 8 10 --runs 300 --r0 3 --gamma 0.2

    # test rapide sans données
    python -m src.run_experiments --synthetic --name demo --k 2 4 6 --runs 50
"""
from __future__ import annotations

import argparse
import json
import time
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from . import plots, sir, verifier
from .data import load_graph, save_graph_json, synthetic_graph
from .selection import (SELECTORS, coverage, cut_weight, select_random, solve_ilp_coverage,
                        solve_ilp_edges, total_weight)

# on rassemble les noms des 12 stratégies, utilisées dans les boucles et les arguments CLI
METHODS = ["random", "degree", "betweenness", "pagerank", "closeness", "kcore",
           "greedy", "ilp", "ilp_deg", "strength", "greedy_edges", "ilp_edges"]
EDGE_METHODS = {"greedy_edges", "ilp_edges"}   # ceux-là optimisent le poids des contacts coupés


# run() représente le cœur des expériences : pour chaque budget et chaque méthode, on choisit les nœuds puis on mesure les résultats
def run(G, ks, methods=METHODS, runs=200, beta=0.02, gamma=0.2, n_seeds=3,
        random_draws=20, ilp_time_limit=60.0, seed=42, out_dir=None, verbose=True,
        major_threshold=0.2, transmission="uniform", seed_policy="fixed"):
    """Pour chaque (méthode, k) : sélection -> couverture -> simulation SIR -> ligne de résultats."""
    # le graphe est converti une seule fois dans le format pratique pour simuler beaucoup de SIR
    p = sir.prepare(G)
    # on récupère le nombre de personnes pour calculer les pourcentages de couverture
    n = p.n
    # le poids total des contacts sert de référence au pourcentage de contacts neutralisés. Le 1 évite une division par 0
    total_w = total_weight(G) or 1.0
    # la liste vide signifie qu’on n’immunise personne : cette baseline sert à mesurer le gain des autres sélections
    base = sir.evaluate(p, [], beta, gamma, runs, n_seeds, seed, major_threshold,
                        transmission=transmission, seed_policy=seed_policy)
    baseline = base["mean"]
    # cette option affiche des informations utiles pendant une exécution, mais peut être désactivée pour les tests
    if verbose:
        print(f"n = {n} personnes, {G.number_of_edges()} arêtes, "
              f"mode={transmission}, beta={beta:.5f}, "
              f"taux d'attaque sans intervention = {baseline:.3f} "
              f"(médiane {base['median']:.3f}, épidémie majeure dans {100 * base['p_major']:.0f} % des cas)")

    # si un dossier de sortie est demandé, on y enregistrera aussi les sélections pour la vérification indépendante
    sol_dir = None
    if out_dir:
        sol_dir = Path(out_dir) / "solutions"
        sol_dir.mkdir(parents=True, exist_ok=True)

    # chauqe combinaison (budget k, méthode) produira une ligne de résultats
    rows = []
    # on parcourt les différents budgets d’immunisation
    for k in ks:
        # pour un même budget, on teste toutes les méthodes choisies
        for method in methods:
            # on ne connaît pas toujours une preuve d’optimalité : seules les méthodes ILP peuvent renvoyer ce statut
            optimal = None
            # on lance un chronomètre précis pour mesurer le temps de sélection, sans inclure le SIR
            t0 = time.perf_counter()
            # la référence aléatoire doit moyenner plusieurs sélections : un seul tirage serait trop variable
            if method == "random":
                # une seule tirage serait trop bruité : on moyenne sur plusieurs tirages
                # chauqe tirage utilise une graine différente pour obtenir des sélections reproductibles
                selections = [select_random(G, k, seed + d) for d in range(random_draws)]
                # on rapporte un temps de sélection moyen par tirage aléatoire.
                dt = (time.perf_counter() - t0) / random_draws
                # pour Random, le programme répartit les répétitions entre tirages, avec au moins 10 SIR par tirage. Le total peut donc dépasser runs
                runs_each = max(10, runs // random_draws)
                # on évalue séparément le risque épidémique de chacune des sélections aléatoires
                evals = [sir.evaluate(p, s, beta, gamma, runs_each, n_seeds, seed, major_threshold,
                                      transmission=transmission, seed_policy=seed_policy)
                         for s in selections]
                # on regroupe les taux observés pour obtenir les statistiques globales de Random
                ev = sir.summarize(np.concatenate([e["rates"] for e in evals]), major_threshold)  # tous les tirages réunis
                # La couverture affichée pour Random est une moyenne sur les différents tirages.
                cov = sum(coverage(G, s) for s in selections) / len(selections)
                # Même principe pour le poids des contacts coupés.
                cut = sum(cut_weight(G, s) for s in selections) / len(selections)
                # pour enregistrer une solution JSON, on conserve seulement le premier tirage (pas toutes les sélections de Random)
                selected = selections[0]
            else:
                # ces 2 méthodes optimisent la couverture ; ilp_deg départage certains optima grâce au degré
                if method in ("ilp", "ilp_deg"):
                    res = solve_ilp_coverage(G, k, ilp_time_limit,
                                             tie_break="degree" if method == "ilp_deg" else None)
                    selected, optimal = res["selected"], res["optimal"]
                # cette variante ILP maximise plutôt le poids des contacts neutralisés
                elif method == "ilp_edges":
                    res = solve_ilp_edges(G, k, ilp_time_limit)
                    selected, optimal = res["selected"], res["optimal"]
                else:
                    # pour les heuristiques/centralités, le dictionnaire SELECTORS appelle directement la fonction correspondante
                    selected = SELECTORS[method](G, k)
                # on arrête le temps de sélection AVANT la simulation SIR
                dt = time.perf_counter() - t0
                # on simule la propagation après avoir immunisé les personnes sélectionnées.
                ev = sir.evaluate(p, selected, beta, gamma, runs, n_seeds, seed, major_threshold,
                                  transmission=transmission, seed_policy=seed_policy)
                # on mesure combien de personnes sont couvertes par la sélection et ses voisins
                cov = coverage(G, selected)
                # on mesure aussi le total des poids des contacts touchés par cette sélection
                cut = cut_weight(G, selected)

            # on rassemble les résultats pour produire ensuite un CSV facile à comparer entre méthodes
            row = {
                # identité de l’essai et mesures combinatoires (nombre et pourcentage)
                "method": method, "k": k, "coverage": cov, "coverage_pct": 100 * cov / n,
                "cut_weight": cut, "cut_pct": 100 * cut / total_w,
                # statistiques de propagation : moyenne, écart-type et médiane des taux d’attaque
                "attack_mean": ev["mean"], "attack_std": ev["std"], "attack_median": ev["median"],
                # demi-largeur approximative de l’intervalle de confiance à 95 %, calculée à partir des répétitions SIR
                "attack_ci95_halfwidth": 1.96 * ev["std"] / np.sqrt(len(ev["rates"])),
                # n_sir_samples permet de voir combien de simulations ont vraiment été agrégées dans cette ligne
                "n_sir_samples": len(ev["rates"]), "transmission": transmission, "seed_policy": seed_policy,
                "p_major": ev["p_major"], "attack_major": ev["attack_major"],
                # gain relatif par rapport à l’absence d’intervention, exprimé en pourcentage
                "reduction_pct": 100 * (1 - ev["mean"] / baseline) if baseline > 0 else 0.0,
                "time_s": dt, "optimal": optimal,
            }
            # on stocke une ligne par méthode et par valeur de k
            rows.append(row)
            if verbose:
                print(f"k={k:<3} {method:<12} couverture={cov:6.1f}  attaque={ev['mean']:.3f}  "
                      f"réduction={row['reduction_pct']:5.1f}%  P(majeure)={ev['p_major']:.2f}  temps={dt:.4f}s")

            # on sauvegarde les identifiants sélectionnés et les métriques pour les contrôler séparément
            if sol_dir:  # solution sauvegardée pour le vérificateur indépendant
                # le nom des JSON contient la méthode et le budget, pour retrouver facilement chaque solution
                (sol_dir / f"{method}_k{k}.json").write_text(json.dumps({
                    "method": method, "k": k, "selected": sorted(int(v) for v in selected),
                    "coverage": coverage(G, selected), "cut_weight": cut_weight(G, selected),
                    "objective": "cut_weight" if method in EDGE_METHODS else "coverage",
                    "optimal": optimal, "time_s": dt,
                }, indent=1), encoding="utf-8")

    # on transforme les lignes accumulées en tableau pandas
    df = pd.DataFrame(rows)
    # les attributs gardent la baseline disponible pour la création des graphiques
    df.attrs["baseline"] = baseline
    df.attrs["baseline_stats"] = {key: base[key] for key in ("mean", "std", "median", "p_major", "attack_major")}
    return df


# main() gère l’interface en ligne de commande et les fichiers écrits sur le disque.
def main(argv=None):
    # on déclare les options de la commande (fichier, budgets, modèle SIR, simulations, etc.)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # chemin du jeu de données réel ; --synthetic permet au contraire un essai sans téléchargement
    ap.add_argument("--input", help="fichier de contacts (.zip Netzschleuder ou .dat/.csv/.gz SocioPatterns)")
    ap.add_argument("--synthetic", action="store_true", help="graphe synthétique (tests uniquement)")
    ap.add_argument("--name", default="run", help="nom du jeu de résultats (dossier results/<name>)")
    # seuil de conservation des contacts : par défaut on conserve les contacts d’au moins 20 secondes
    ap.add_argument("--min-contacts", type=int, default=1, help="nb min d'intervalles de 20 s pour garder une arête")
    # on peut fournir plusieurs valeurs de k dans une même expérience
    ap.add_argument("--k", type=int, nargs="+", default=[2, 4, 6, 8, 10])
    ap.add_argument("--methods", nargs="+", default=METHODS, choices=METHODS)
    # nombre de sélections aléatoires indépendantes utilisées pour la baseline Random
    ap.add_argument("--random-draws", type=int, default=20, help="nombre de sélections aléatoires indépendantes")
    # nombre demandé de simulations SIR pour une sélection fixe
    ap.add_argument("--runs", type=int, default=200, help="nb de simulations SIR par sélection")
    # en uniforme, le modèle peut calibrer beta pour viser ce R0
    ap.add_argument("--r0", type=float, default=3.0, help="R0 visé : beta est calibré sur le graphe")
    ap.add_argument("--beta", type=float, default=None, help="force beta (ignore --r0 et --target-attack)")
    # on peut aussi calibrer beta pour atteindre un taux d’attaque de référence, surtout en pondéré
    ap.add_argument("--target-attack", type=float, default=None,
                    help="calibre beta par simulation pour ce taux d'attaque de référence, recommandé en weighted")
    ap.add_argument("--calibration-runs", type=int, default=60,
                    help="simulations par évaluation pour la calibration")
    # 2 façons de transmettre : uniforme ou dépendante de la durée du contact
    ap.add_argument("--transmission", choices=["uniform", "weighted"], default="uniform",
                    help="probabilité identique ou dépendante de la durée des contacts")
    # fixed et resample définissent comment choisir les cas infectés au départ.
    ap.add_argument("--seed-policy", choices=["fixed", "resample"], default="fixed",
                    help="fixed conserve les mêmes cas initiaux candidats, même si immunisés")
    ap.add_argument("--seed", type=int, default=42, help="graine de base Monte-Carlo")
    ap.add_argument("--gamma", type=float, default=0.2)
    ap.add_argument("--seeds", type=int, default=3, help="nb de cas initiaux")
    ap.add_argument("--ilp-time-limit", type=float, default=60.0)
    # une simulation est dite majeure si son taux d’attaque dépasse ce seuil
    ap.add_argument("--major-threshold", type=float, default=0.2,
                    help="taux d'attaque à partir duquel une simulation compte comme épidémie majeure")
    # lecture des paramètres effectivement fournis au lancement
    args = ap.parse_args(argv)
    # on refuse les nombres de simulations impossibles ou nuls avant de commencer
    if args.runs < 1 or args.random_draws < 1 or args.calibration_runs < 1:
        ap.error("--runs, --random-draws et --calibration-runs doivent être >= 1")
    # un temps limite ILP doit être strictement positif
    if args.ilp_time_limit <= 0:
        ap.error("--ilp-time-limit doit être > 0")
    # Gamma est une probabilité : sa valeur doit être dans l’intervalle autorisé
    if not 0 < args.gamma <= 1:
        ap.error("--gamma doit être dans ]0,1]")
    # en pondéré, on impose beta ou une cible de calibration plutôt que le calibrage R0 uniforme
    if args.transmission == "weighted" and args.target_attack is None and args.beta is None:
        ap.error("en mode weighted, choisir --target-attack ou --beta ; --r0 est seulement valide pour uniform")
    if args.target_attack is not None and not 0 < args.target_attack < 1:
        ap.error("--target-attack doit être dans ]0,1[")
    # Backend sans fenêtre, utile pour générer des PNG depuis le terminal.
    matplotlib.use("Agg")  # en ligne de commande on enregistre les PNG, sans ouvrir de fenêtre

    # on charge soit un petit graphe artificiel, soit des contacts réels
    if args.synthetic:
        G = synthetic_graph(seed=0)
    elif args.input:
        G = load_graph(args.input, args.min_contacts)
    else:
        ap.error("donne --input <fichier> ou --synthetic")

    # le nom du dossier est filtré pour éviter les caractères inattendus dans les chemins
    if not args.name.replace("_", "").replace("-", "").isalnum():
        ap.error("--name ne doit contenir que lettres, chiffres, tiret ou underscore")
    # un budget ne peut pas dépasser le nombre de personnes disponibles
    if any(k < 0 or k > G.number_of_nodes() for k in args.k):
        ap.error(f"les valeurs de --k doivent être entre 0 et {G.number_of_nodes()}")
    # les sorties sont rangées dans un sous-dossier au nom de l’expérience
    out_dir = Path("results") / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    # on conserve une copie du graphe préparé pour le vérificateur
    graph_path = Path("data/processed") / f"{args.name}_graph.json"
    save_graph_json(G, graph_path)  # données dérivées : NON commitées (voir .gitignore)

    # on choisit la méthode de fixation de beta selon la priorité : beta explicite, cible d’attaque ou R0
    calibration = None
    # si la personne a fourni beta, il n’y a pas besoin de le recalculer
    if args.beta is not None:
        beta = args.beta
    # Sinon on cherche beta par simulations pour approcher une attaque de référence.
    elif args.target_attack is not None:
        # la calibration appelle plusieurs simulations SIR à différentes valeurs de beta
        calibration = sir.calibrate_beta_for_attack(
            sir.prepare(G), target=args.target_attack, gamma=args.gamma,
            n_seeds=args.seeds, n_runs=args.calibration_runs, base_seed=args.seed + 100000,
            transmission=args.transmission, seed_policy=args.seed_policy)
        beta = calibration["beta"]
        print(f"Calibration cible={args.target_attack:.3f}, obtenu={calibration['attack']:.3f}, "
              f"atteinte={calibration['reached']}")
        # on prévient si la calibration n’a pas suffisamment approché sa cible
        if not calibration["reached"]:
            print("ATTENTION : cible non atteinte à 5 points près ; à signaler dans l'analyse")
    else:
        # dernier cas : beta est déterminé à partir du R0 cible (uniforme)
        beta = sir.beta_for_r0(G, args.gamma, args.r0)
    if not 0 <= beta <= 1:
        ap.error("beta calculé hors de [0,1] ; adapter R0, gamma ou utiliser --target-attack")
    print(f"beta = {beta:.4f}, gamma = {args.gamma}")
    # on lance enfin toutes les méthodes avec les paramètres vérifiés
    df = run(G, args.k, args.methods, args.runs, beta, args.gamma, args.seeds,
             random_draws=args.random_draws, ilp_time_limit=args.ilp_time_limit,
             seed=args.seed, out_dir=out_dir, major_threshold=args.major_threshold,
             transmission=args.transmission, seed_policy=args.seed_policy)
    # le CSV conserve une ligne par méthode et budget
    df.to_csv(out_dir / "results.csv", index=False)
    # le JSON conserve la configuration exacte et les métadonnées pour reproduire l’expérience
    config = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input) if args.input else "synthetic(seed=0)",
        "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(),
        "min_contacts": args.min_contacts, "k": args.k, "methods": args.methods,
        "runs": args.runs, "random_draws": args.random_draws,
        "gamma": args.gamma, "beta": beta, "r0_target": args.r0 if args.beta is None and args.target_attack is None else None,
        "target_attack": args.target_attack, "calibration": calibration,
        "n_seeds": args.seeds, "seed": args.seed, "transmission": args.transmission,
        "seed_policy": args.seed_policy, "ilp_time_limit": args.ilp_time_limit,
        "baseline": {key: df.attrs["baseline_stats"][key] for key in ("mean", "std", "median", "p_major")},
        "python": sys.version.split()[0], "platform": platform.platform(),
    }
    # on écrit la configuration en texte UTF-8 pour pouvoir la consulter facilement
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    # On génère les cinq représentations principales des résultats numériques
    plots.plot_attack_rate(df, df.attrs["baseline"], out_dir / "attack_rate_vs_k.png")
    plots.plot_major_outbreak(df, df.attrs["baseline_stats"]["p_major"], out_dir / "p_major_vs_k.png")
    plots.plot_objective_alignment(df, max(args.k), out_dir / "objective_vs_attack.png")
    plots.plot_time(df, out_dir / "time_vs_k.png")
    plots.plot_quality_vs_time(df, max(args.k), out_dir / "quality_vs_time.png")
    print(f"\nRésultats dans {out_dir}/ ; graphe dans {graph_path}")

    # on recalcule les contraintes/métriques des solutions JSON à partir du graphe sauvegardé
    print("\n--- Vérification indépendante ---")
    # Le mode strict refuse notamment des solutions sans les métriques attendues
    errors = verifier.verify(graph_path, out_dir / "solutions", strict=True)
    # si il y a des solutions non conformes, on stoppe avec un message explicite
    if errors:
        raise SystemExit(f"ERREUR: {errors} solution(s) non conformes")


if __name__ == "__main__":
    main()
