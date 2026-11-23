# Projet E2 : Validation de données cliniques FHIR avec SHACL

## Groupe9

| Membre | Contribution principale |
|---|---|
| @AntoV789264 | Création des règles SHACL, implémentation du `shacl_engine.py` |
| @Blak024 | Création des données RDF mockées, script `naive_engine.py` |
| @Seluj3110 | Point d'entrée `main.py`, notebook de démo, rédaction des slides |

## Sujet

- **Identifiant du catalogue :** E2 — Valider des données cliniques FHIR avec SHACL
- **Problématique :** Les dossiers patients s'échangent au format FHIR, mais une donnée syntaxiquement correcte (JSON valide) peut être cliniquement incohérente (ex: date de décès antérieure à une naissance). Les scripts de validation codés en dur sont difficiles à maintenir à grande échelle.
- **MVP :** Génération synthétique de 1000 patients avec injection d'anomalies cliniques, création d'une bibliothèque de formes SHACL, et détection via un raisonneur symbolique.

## Architecture

Le projet adopte une architecture modulaire séparant les données, les règles et les moteurs d'exécution :
- `data/` : Contient la base de connaissances médicale (`shapes.ttl`). La base de patients (`patients_db.ttl`) y est générée localement à l'exécution (ignorée par Git).
- `src/generator.py` : Script générant dynamiquement 1000 patients.
- `src/shacl_engine.py` : Module principal utilisant `pyshacl` pour valider le graphe RDF contre les règles cliniques.
- `src/naive_engine.py` : Module de comparaison contenant l'approche algorithmique classique (script en dur).
- `main.py` : Point d'entrée en ligne de commande (CLI) orchestrant la validation et mesurant les performances.
- `demo.ipynb` : Notebook interactif reprenant la logique pour la démonstration.

## Installation

```bash
# Création d'un environnement virtuel
python -m venv venv

# Installation des dépendances figées
pip install -r requirements.txt
```

## Utilisation

```bash
cd Groupe9
python main.py
```

## Tests

```bash
cd Groupe9
python main.py
```

## Résultats et évaluation

- **Baseline :** Notre baseline est une fonction Python classique vérifiant les dates avec des conditions if/else.
- **Protocole :** Le script `main.py` chronomètre l'exécution des deux approches et compare la complexité de maintenance.
- **Métriques et interprétation :** Le script naïf s'exécute quasi instantanément sur un patient unique. Le moteur SHACL, lui, analyse les 1000 dossiers en environ 16 secondes. Cependant, l'approche SHACL prouve son énorme avantage métier : elle permet de séparer complètement la logique médicale de l'exécution. L'ajout de 500 nouvelles règles de validation se ferait uniquement en enrichissant le fichier `shapes.ttl`, sans avoir à modifier, retester ou recompiler le moindre script Python.

## Limites et plan B

- **Limites connues :** Pour ce MVP, nous n'avons pas implémenté le pipeline complet de conversion JSON-LD / FHIR vers RDF, qui est complexe. Nous avons injecté des données directement modélisées en Turtle (RDF) simulant l'export d'un patient Synthea.
- **Dépendances externes :** `pyshacl` et `rdflib`.
- **Plan B :** En cas de défaillance matérielle lors de la soutenance, les autres membres disposeront du notebook en local.

## Répartition du travail

- **@AntoV789264** a pris en charge la recherche sur la syntaxe SHACL/SPARQL pour formuler les contraintes médicales.
- **@Blak024** s'est occupé de la structure des données RDF et de la baseline classique pour le comparatif.
- **@Seluj3110** a structuré le dépôt (modularisation), géré l'intégration sur GitHub, et préparé les livrables de soutenance.

*Le groupe a collaboré via des sessions de travail partagées et des commits réguliers sur le dépôt distant.*

## Licence et références

- **Code source :** Distribué sous licence MIT.
- **Bibliothèques :** `rdflib` et `pyshacl`.
- Standard W3C SHACL : [https://www.w3.org/TR/shacl/](https://www.w3.org/TR/shacl/)
- Représentation FHIR RDF (HL7) : [https://hl7.org/fhir/rdf.html](https://hl7.org/fhir/rdf.html)