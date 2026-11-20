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

METHODS = ["random", "degree", "betweenness", "pagerank", "closeness", "kcore",
           "greedy", "ilp", "ilp_deg", "strength", "greedy_edges", "ilp_edges"]
EDGE_METHODS = {"greedy_edges", "ilp_edges"}   # ceux-là optimisent le poids des contacts coupés


def run(G, ks, methods=METHODS, runs=200, beta=0.02, gamma=0.2, n_seeds=3,
        random_draws=20, ilp_time_limit=60.0, seed=42, out_dir=None, verbose=True,
        major_threshold=0.2, transmission="uniform", seed_policy="fixed"):
    """Pour chaque (méthode, k) : sélection -> couverture -> simulation SIR -> ligne de résultats."""
    p = sir.prepare(G)
    n = p.n
    total_w = total_weight(G) or 1.0
    base = sir.evaluate(p, [], beta, gamma, runs, n_seeds, seed, major_threshold,
                        transmission=transmission, seed_policy=seed_policy)
    baseline = base["mean"]
    if verbose:
        print(f"n = {n} personnes, {G.number_of_edges()} arêtes, "
              f"mode={transmission}, beta={beta:.5f}, "
              f"taux d'attaque sans intervention = {baseline:.3f} "
              f"(médiane {base['median']:.3f}, épidémie majeure dans {100 * base['p_major']:.0f} % des cas)")

    sol_dir = None
    if out_dir:
        sol_dir = Path(out_dir) / "solutions"
        sol_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for k in ks:
        for method in methods:
            optimal = None
            t0 = time.perf_counter()
            if method == "random":
                # une seule tirage serait trop bruité : on moyenne sur plusieurs tirages
                selections = [select_random(G, k, seed + d) for d in range(random_draws)]
                dt = (time.perf_counter() - t0) / random_draws
                runs_each = max(10, runs // random_draws)
                evals = [sir.evaluate(p, s, beta, gamma, runs_each, n_seeds, seed, major_threshold,
                                      transmission=transmission, seed_policy=seed_policy)
                         for s in selections]
                ev = sir.summarize(np.concatenate([e["rates"] for e in evals]), major_threshold)  # tous les tirages réunis
                cov = sum(coverage(G, s) for s in selections) / len(selections)
                cut = sum(cut_weight(G, s) for s in selections) / len(selections)
                selected = selections[0]
            else:
                if method in ("ilp", "ilp_deg"):
                    res = solve_ilp_coverage(G, k, ilp_time_limit,
                                             tie_break="degree" if method == "ilp_deg" else None)
                    selected, optimal = res["selected"], res["optimal"]
                elif method == "ilp_edges":
                    res = solve_ilp_edges(G, k, ilp_time_limit)
                    selected, optimal = res["selected"], res["optimal"]
                else:
                    selected = SELECTORS[method](G, k)
                dt = time.perf_counter() - t0
                ev = sir.evaluate(p, selected, beta, gamma, runs, n_seeds, seed, major_threshold,
                                  transmission=transmission, seed_policy=seed_policy)
                cov = coverage(G, selected)
                cut = cut_weight(G, selected)

            row = {
                "method": method, "k": k, "coverage": cov, "coverage_pct": 100 * cov / n,
                "cut_weight": cut, "cut_pct": 100 * cut / total_w,
                "attack_mean": ev["mean"], "attack_std": ev["std"], "attack_median": ev["median"],
                "attack_ci95_halfwidth": 1.96 * ev["std"] / np.sqrt(len(ev["rates"])),
                "n_sir_samples": len(ev["rates"]), "transmission": transmission, "seed_policy": seed_policy,
                "p_major": ev["p_major"], "attack_major": ev["attack_major"],
                "reduction_pct": 100 * (1 - ev["mean"] / baseline) if baseline > 0 else 0.0,
                "time_s": dt, "optimal": optimal,
            }
            rows.append(row)
            if verbose:
                print(f"k={k:<3} {method:<12} couverture={cov:6.1f}  attaque={ev['mean']:.3f}  "
                      f"réduction={row['reduction_pct']:5.1f}%  P(majeure)={ev['p_major']:.2f}  temps={dt:.4f}s")

            if sol_dir:  # solution sauvegardée pour le vérificateur indépendant
                (sol_dir / f"{method}_k{k}.json").write_text(json.dumps({
                    "method": method, "k": k, "selected": sorted(int(v) for v in selected),
                    "coverage": coverage(G, selected), "cut_weight": cut_weight(G, selected),
                    "objective": "cut_weight" if method in EDGE_METHODS else "coverage",
                    "optimal": optimal, "time_s": dt,
                }, indent=1), encoding="utf-8")

    df = pd.DataFrame(rows)
    df.attrs["baseline"] = baseline
    df.attrs["baseline_stats"] = {key: base[key] for key in ("mean", "std", "median", "p_major", "attack_major")}
    return df


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="fichier de contacts (.zip Netzschleuder ou .dat/.csv/.gz SocioPatterns)")
    ap.add_argument("--synthetic", action="store_true", help="graphe synthétique (tests uniquement)")
    ap.add_argument("--name", default="run", help="nom du jeu de résultats (dossier results/<name>)")
    ap.add_argument("--min-contacts", type=int, default=1, help="nb min d'intervalles de 20 s pour garder une arête")
    ap.add_argument("--k", type=int, nargs="+", default=[2, 4, 6, 8, 10])
    ap.add_argument("--methods", nargs="+", default=METHODS, choices=METHODS)
    ap.add_argument("--random-draws", type=int, default=20, help="nombre de sélections aléatoires indépendantes")
    ap.add_argument("--runs", type=int, default=200, help="nb de simulations SIR par sélection")
    ap.add_argument("--r0", type=float, default=3.0, help="R0 visé : beta est calibré sur le graphe")
    ap.add_argument("--beta", type=float, default=None, help="force beta (ignore --r0 et --target-attack)")
    ap.add_argument("--target-attack", type=float, default=None,
                    help="calibre beta par simulation pour ce taux d'attaque de référence, recommandé en weighted")
    ap.add_argument("--calibration-runs", type=int, default=60,
                    help="simulations par évaluation pour la calibration")
    ap.add_argument("--transmission", choices=["uniform", "weighted"], default="uniform",
                    help="probabilité identique ou dépendante de la durée des contacts")
    ap.add_argument("--seed-policy", choices=["fixed", "resample"], default="fixed",
                    help="fixed conserve les mêmes cas initiaux candidats, même si immunisés")
    ap.add_argument("--seed", type=int, default=42, help="graine de base Monte-Carlo")
    ap.add_argument("--gamma", type=float, default=0.2)
    ap.add_argument("--seeds", type=int, default=3, help="nb de cas initiaux")
    ap.add_argument("--ilp-time-limit", type=float, default=60.0)
    ap.add_argument("--major-threshold", type=float, default=0.2,
                    help="taux d'attaque à partir duquel une simulation compte comme épidémie majeure")
    args = ap.parse_args(argv)
    if args.runs < 1 or args.random_draws < 1 or args.calibration_runs < 1:
        ap.error("--runs, --random-draws et --calibration-runs doivent être >= 1")
    if args.ilp_time_limit <= 0:
        ap.error("--ilp-time-limit doit être > 0")
    if not 0 < args.gamma <= 1:
        ap.error("--gamma doit être dans ]0,1]")
    if args.transmission == "weighted" and args.target_attack is None and args.beta is None:
        ap.error("en mode weighted, choisir --target-attack ou --beta ; --r0 est seulement valide pour uniform")
    if args.target_attack is not None and not 0 < args.target_attack < 1:
        ap.error("--target-attack doit être dans ]0,1[")
    matplotlib.use("Agg")  # en ligne de commande on enregistre les PNG, sans ouvrir de fenêtre

    if args.synthetic:
        G = synthetic_graph(seed=0)
    elif args.input:
        G = load_graph(args.input, args.min_contacts)
    else:
        ap.error("donne --input <fichier> ou --synthetic")

    if not args.name.replace("_", "").replace("-", "").isalnum():
        ap.error("--name ne doit contenir que lettres, chiffres, tiret ou underscore")
    if any(k < 0 or k > G.number_of_nodes() for k in args.k):
        ap.error(f"les valeurs de --k doivent être entre 0 et {G.number_of_nodes()}")
    out_dir = Path("results") / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_path = Path("data/processed") / f"{args.name}_graph.json"
    save_graph_json(G, graph_path)  # données dérivées : NON commitées (voir .gitignore)

    calibration = None
    if args.beta is not None:
        beta = args.beta
    elif args.target_attack is not None:
        calibration = sir.calibrate_beta_for_attack(
            sir.prepare(G), target=args.target_attack, gamma=args.gamma,
            n_seeds=args.seeds, n_runs=args.calibration_runs, base_seed=args.seed + 100000,
            transmission=args.transmission, seed_policy=args.seed_policy)
        beta = calibration["beta"]
        print(f"Calibration cible={args.target_attack:.3f}, obtenu={calibration['attack']:.3f}, "
              f"atteinte={calibration['reached']}")
        if not calibration["reached"]:
            print("ATTENTION : cible non atteinte à 5 points près ; à signaler dans l'analyse")
    else:
        beta = sir.beta_for_r0(G, args.gamma, args.r0)
    if not 0 <= beta <= 1:
        ap.error("beta calculé hors de [0,1] ; adapter R0, gamma ou utiliser --target-attack")
    print(f"beta = {beta:.4f}, gamma = {args.gamma}")
    df = run(G, args.k, args.methods, args.runs, beta, args.gamma, args.seeds,
             random_draws=args.random_draws, ilp_time_limit=args.ilp_time_limit,
             seed=args.seed, out_dir=out_dir, major_threshold=args.major_threshold,
             transmission=args.transmission, seed_policy=args.seed_policy)
    df.to_csv(out_dir / "results.csv", index=False)
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
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    plots.plot_attack_rate(df, df.attrs["baseline"], out_dir / "attack_rate_vs_k.png")
    plots.plot_major_outbreak(df, df.attrs["baseline_stats"]["p_major"], out_dir / "p_major_vs_k.png")
    plots.plot_objective_alignment(df, max(args.k), out_dir / "objective_vs_attack.png")
    plots.plot_time(df, out_dir / "time_vs_k.png")
    plots.plot_quality_vs_time(df, max(args.k), out_dir / "quality_vs_time.png")
    print(f"\nRésultats dans {out_dir}/ ; graphe dans {graph_path}")

    print("\n--- Vérification indépendante ---")
    errors = verifier.verify(graph_path, out_dir / "solutions", strict=True)
    if errors:
        raise SystemExit(f"ERREUR: {errors} solution(s) non conformes")


if __name__ == "__main__":
    main()
