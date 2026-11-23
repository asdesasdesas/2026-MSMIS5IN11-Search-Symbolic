"""Reproduire les 3 expériences documentées, sans conserver les données brutes dans Git.

Depuis groupe-b5 :
    python scripts/reproduce_examples.py
    python scripts/reproduce_examples.py --quick

Les fichiers contacts doivent être présents dans data/raw/ ; voir data/README.md.
Sans --quick : on relance le protocole final (200 simulations et 10 tirages aléatoires)
et les résultats sont créés localement dans results/<nom>_final/.
En mode --quick : on utilise des paramètres réduits pour la démonstration ;
les sorties sont écrites dans results/<nom>_quick/ pour ne pas écraser les résultats finaux.
Les fichiers conservés dans results/examples/ ne sont pas modifiés par ce script.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# on retrouve la racine du projet, même si ce script est lancé depuis le dossier scripts/
ROOT = Path(__file__).resolve().parents[1]


# cette fonction prépare les trois expériences et les exécute à la suite
def main(argv=None):
    # argparse permet de lire les options ajoutées à la commande dans le terminal
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--quick', action='store_true', help='exécution très courte de démonstration')
    # on récupère les options choisies par la personne qui lance le script
    args = ap.parse_args(argv)
    # on liste les deux fichiers de données indispensables aux expériences
    required = [ROOT / 'data/raw/hospital.dat.gz', ROOT / 'data/raw/primaryschool.csv.gz']
    # on repère les fichiers absents et on prépare un message avec leurs chemins relatifs
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    # si un jeu de données manque, on arrête avant de lancer des calculs inutiles
    if missing:
        print('Données manquantes :', ', '.join(missing))
        print('Lancer : python data/download_data.py hospital_raw')
        print('Puis     : python data/download_data.py primary_school_raw')
        return 2
    # le protocol final utilise 200 simulations SIR par sélection ; en mode démo on en fait moins.
    runs_hospital, runs_school, calibration_runs = (10, 10, 12) if args.quick else (200, 200, 100)
    # les expériences finales utilisent dix tirages de sélections aléatoires
    random_draws = 5 if args.quick else 10
    # chauqe entrée précise le nom de l’expérience, les données, les budgets k et les options SIR
    configs = [
        ('hospital_uniform_final', 'data/raw/hospital.dat.gz', [2, 6, 10], ['--r0', '3']),
        ('hospital_weighted_final', 'data/raw/hospital.dat.gz', [2, 6, 10],
         ['--transmission','weighted','--target-attack','0.75','--calibration-runs',str(calibration_runs)]),
        ('primary_uniform_final','data/raw/primaryschool.csv.gz',[5,12],['--r0','3']),
    ]
    # on construit une commande complète pour chaque expérience
    for name, source, budgets, extra in configs:
        # le nombre de répétitions dépend ici du réseau utilisé
        runs = runs_school if name.startswith('primary_uniform') else runs_hospital
        # l’école reçoit une limite de temps ILP plus courte que l’hôpital
        tlim = 8 if name.startswith('primary_uniform') else 12
        # En mode rapide on change le nom pour ne pas écraser une exécution finale existante
        output_name = name.replace('_final', '_quick') if args.quick else name
        # sys.executable utilise le Python de notre environnement ; -m lance le module des expériences
        cmd = [sys.executable,'-m','src.run_experiments','--input',source,'--name',output_name,
               '--k',*map(str,budgets),'--runs',str(runs),'--random-draws',str(random_draws),
               '--seed-policy','fixed','--seed','42','--ilp-time-limit',str(tlim),*extra]
        # on affiche le nom pour suivre l’avancement des trois exécutions
        print('\nEXPERIENCE :',output_name, flush=True)
        # on exécute réellement la commande depuis le projet. check=True signale un échec
        subprocess.run(cmd,cwd=ROOT,check=True)
    print('\nExécutions terminées. Les sorties sont dans results/<nom>_final/ (ou results/<nom>_quick/).')
    print('Comparer les exécutions finales avec les fichiers de référence dans results/examples/.')
    return 0


# ce bloc ne s’exécute que si on lance directement ce fichier.
if __name__ == '__main__':
    # le code de retour de main() devient le code de sortie du programme.
    raise SystemExit(main())
