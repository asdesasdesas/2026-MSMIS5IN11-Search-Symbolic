"""Reproduire les 3 expériences documentées, sans conserver les données brutes dans Git.

Depuis groupe-b5 :
    python scripts/reproduce_examples.py
    python scripts/reproduce_examples.py --quick

Les fichiers contacts doivent être présents dans data/raw/ ; voir data/README.md.
En mode --quick les paramètres sont réduits pour la démo (résultats NON comparables
aux fichiers conservés dans results/examples/).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--quick', action='store_true', help='exécution très courte de démonstration')
    args = ap.parse_args(argv)
    required = [ROOT / 'data/raw/hospital.dat.gz', ROOT / 'data/raw/primaryschool.csv.gz']
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print('Données manquantes :', ', '.join(missing))
        print('Lancer : python data/download_data.py hospital_raw')
        print('Puis     : python data/download_data.py primary_school_raw')
        return 2
    runs_hospital, runs_school, calibration_runs = (10, 10, 12) if args.quick else (55, 35, 30)
    configs = [
        ('hospital_uniform', 'data/raw/hospital.dat.gz', [2, 6, 10], ['--r0', '3']),
        ('hospital_weighted', 'data/raw/hospital.dat.gz', [2, 6, 10],
         ['--transmission','weighted','--target-attack','0.75','--calibration-runs',str(calibration_runs)]),
        ('primary_uniform','data/raw/primaryschool.csv.gz',[5,12],['--r0','3']),
    ]
    for name, source, budgets, extra in configs:
        runs = runs_school if name == 'primary_uniform' else runs_hospital
        tlim = 8 if name == 'primary_uniform' else 12
        cmd = [sys.executable,'-m','src.run_experiments','--input',source,'--name',name,
               '--k',*map(str,budgets),'--runs',str(runs),'--random-draws','5',
               '--seed-policy','fixed','--seed','42','--ilp-time-limit',str(tlim),*extra]
        print('\nEXPERIENCE :',name, flush=True)
        subprocess.run(cmd,cwd=ROOT,check=True)
    print('\nReproduction terminée, comparer results/<nom>/ avec results/examples/<nom>/.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
