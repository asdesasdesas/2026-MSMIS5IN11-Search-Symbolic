"""Télécharge un jeu de données SocioPatterns dans data/raw/ (jamais commité, voir .gitignore).

    python data/download_data.py hospital
    python data/download_data.py high_school_2011

Les fichiers viennent de Netzschleuder (miroir des jeux SocioPatterns, même contenu).
Pour l'école primaire, le téléchargement est manuel (lien affiché ci-dessous) :
le format brut "t i j Ci Cj" est lu directement par src/data.py.

Licence des données : CC BY-NC-SA 3.0. Il faut citer SocioPatterns (http://www.sociopatterns.org)
et l'article d'origine (voir README).
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATASETS = {
    "hospital": "https://networks.skewed.de/net/sp_hospital/files/sp_hospital.csv.zip",
    "high_school_2011": "https://networks.skewed.de/net/sp_high_school_new/files/2011.csv.zip",
    "high_school_2012": "https://networks.skewed.de/net/sp_high_school_new/files/2012.csv.zip",
    # Fichiers bruts SocioPatterns, tels qu'utilisés pour les expériences du projet.
    "hospital_raw": "https://sociopatterns.org/assets/data/hospital_lyon_contacts.dat.gz",
    "primary_school_raw": "https://www.sociopatterns.org/wp-content/uploads/2015/09/primaryschool.csv.gz",
}
MANUAL = {
    "primary_school": "http://www.sociopatterns.org/datasets/primary-school-temporal-network-data/",
}
RAW_DIR = Path(__file__).resolve().parent / "raw"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in {**DATASETS, **MANUAL}:
        print("Usage : python data/download_data.py <" + "|".join({**DATASETS, **MANUAL}) + ">")
        sys.exit(2)
    name = argv[0]
    if name in MANUAL:
        print(f"Téléchargement manuel : ouvre {MANUAL[name]}, télécharge le fichier "
              f"(.csv.gz) et mets-le dans {RAW_DIR}")
        return
    url = DATASETS[name]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if name == "hospital_raw":
        filename = "hospital.dat.gz"
    elif name == "primary_school_raw":
        filename = "primaryschool.csv.gz"
    else:
        filename = name + ".csv.zip"
    dest = RAW_DIR / filename
    print(f"Téléchargement de {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (projet-b5)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()              # on lit tout AVANT d'écrire : pas de fichier partiel
        if dest.suffix == ".gz" and not content.startswith(b"\x1f\x8b"):
            raise ValueError("le serveur n'a pas renvoyé une archive gzip valide")
        if dest.suffix == ".zip" and not content.startswith(b"PK"):
            raise ValueError("le serveur n'a pas renvoyé une archive ZIP valide")
        dest.write_bytes(content)
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        print(f"Echec ({err}). Télécharge le fichier à la main depuis {url} "
              f"et place-le dans {RAW_DIR}")
        sys.exit(1)
    print(f"OK -> {dest} ({dest.stat().st_size / 1024:.0f} Ko)")
    print(f"Lancer : python -m src.run_experiments --input data/raw/{dest.name} --name {name}")


if __name__ == "__main__":
    main()
