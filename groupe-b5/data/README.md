
# Données utilisées dans le projet B5

## 1. Origine des données

Nous utilisons des jeux de données publics provenant du projet [SocioPatterns](http://www.sociopatterns.org/datasets/), qui étudie les interactions entre individus à l'aide de capteurs de proximité.

Nous avons utilisé deux réseaux de contacts :
- Un réseau hospitalier, constitué de 75 personnes.
- Un réseau d'école primaire, constitué de 242 personnes.

Ces données nous permettent d'étudier différentes stratégies de sélection de personnes à immuniser sur des réseaux réels.

## 2. Construction des graphes

Les contacts sont enregistrés par intervalles de 20 secondes.

Notre programme `src/data.py` transforme ces données en graphes non orientés et pondérés :

- Un nœud représente une personne.
- Une arête représente un contact entre deux personnes.
- Le poids d'une arête correspond au nombre d'intervalles de contact observés entre ces personnes.

Les contacts répétés entre deux personnes sont regroupés dans une même arête.

Nous utilisons principalement `min_contacts = 1`, ce qui permet de conserver tous les contacts enregistrés.

Après ce traitement, les graphes utilisés comportent :

| Jeu de données | Nœuds | Arêtes |
|---|---:|---:|
| Hôpital | 75 | 1 139 |
| École primaire | 242 | 8 317 |

## 3. Téléchargement des données

Depuis le dossier `groupe-b5`, exécuter :

```bash
python data/download_data.py hospital_raw
python data/download_data.py primary_school_raw
```

Les fichiers attendus sont :

- `data/raw/hospital.dat.gz`
- `data/raw/primaryschool.csv.gz`

Si le téléchargement automatique échoue, les archives peuvent être récupérées manuellement depuis les pages SocioPatterns correspondantes.

## 4. Organisation du dossier

- `download_data.py` : script de téléchargement des jeux de données.
- `raw/` : données originales téléchargées.
- `processed/` : graphes générés lors des expériences.
- `README.md` : documentation des données.

## 5. Données et reproductibilité

Les fichiers de données téléchargées et les graphes générés ne sont pas versionnés dans notre dépôt GitHub.

Nous conservons les scripts permettant de télécharger les données, de construire les graphes et de reproduire les expériences.

L'agrégation en graphe statique entraîne une perte de l'ordre chronologique des contacts. Cette limite est prise en compte dans notre analyse méthodologique.
