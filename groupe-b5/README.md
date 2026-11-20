# B5 — Qui tester en priorité ? Optimisation sur un graphe de contacts

> Projet pédagogique EPF · optimisation combinatoire, ILP, algorithmes gloutons et graphes de contacts SocioPatterns. **La simulation SIR sert à évaluer les sélections ; ce n'est pas un projet d'apprentissage supervisé.**

## 1. Groupe et contributions proposées

| Membre GitHub | Contribution principale envisagée | Parties associées |
|---|---|---|
| **@pseudo1** | Modélisation de données, construction des graphes, simulation SIR uniforme et pondérée, analyses médicales, tests SIR | `src/data.py`, `src/sir.py`, `data/`, `tests/test_sir.py`, `docs/ANALYSE_METHODOLOGIQUE.md` |
| **@pseudo2** | Optimisation ILP et gloutonne, baselines de centralité, vérificateur indépendant, pipeline d'expériences et graphiques | `src/selection.py`, `src/verifier.py`, `src/run_experiments.py`, `src/plots.py`, `tests/` |
| **Les deux** | Relecture croisée, notebook, présentation, reproductibilité, validation des résultats et PR | `notebooks/`, `slides/`, `README.md`, `results/examples/` |

**Important : cette répartition est une PROPOSITION de documentation**, pas une preuve de travail réalisé. Remplacer les deux pseudos par les vrais comptes GitHub et corriger les missions selon vos contributions réelles avant la PR. Aucun historique Git ne peut être recréé à partir d'un ZIP ; ne pas simuler de commits.

## 2. Sujet, problématique, MVP

- **Sujet du catalogue : B5.** Avec un budget limité `k` de vaccins ou d'isolements, quels individus choisir pour maximiser la couverture d'un graphe de contacts, et quels effets ont ces choix sur la propagation simulée ?
- **MVP réalisé :** construction de graphes SocioPatterns (hôpital, école primaire), ILP exact pour couverture, glouton monotone sous-modulaire, baselines aléatoire/degré/centralités, simulations SIR, mesures de qualité et de temps, vérificateur indépendant, tests automatisés.
- **Extensions réalisées :** objectif alternatif de contacts pondérés coupés (`greedy_edges`, `ilp_edges`), départage des optimums de couverture par degré (`ilp_deg`), centralités `closeness` et `kcore`, scénario de transmission SIR pondérée par durée, calibration optionnelle de `beta` par taux d'attaque cible.
- **Non réalisé :** graphe temporel et budgets différenciés. Ces éléments sont des perspectives, pas des fonctionnalités à promettre dans la soutenance.

### Interprétation médicale

Le modèle SIR suppose que les personnes ciblées sont **immédiatement immunisées ou parfaitement isolées**. Cela ne modélise **pas** le dépistage seul ; un vrai test exige de tenir compte du résultat, de la sensibilité/spécificité et des actions qui suivent. C'est un scénario idéal de prévention, non une recommandation clinique. Voir `docs/ANALYSE_METHODOLOGIQUE.md`.

## 3. Architecture

```text
data/download_data.py      # téléchargement (données exclues du dépôt)
       │
       ▼
src/data.py               # t, i, j, catégories -> graphe statique pondéré
       │
       ├── src/selection.py  # aléatoire, centralités, gloutons, ILP (HiGHS)
       │
       ├── src/sir.py        # évaluation SIR uniforme OU pondérée
       │
       ▼
src/run_experiments.py   # budget k, métriques, CSV, config JSON, PNG
       │
       ├── src/plots.py           # visualisations
       └── src/verifier.py        # contrôle indépendant via JSON (standard library)

notebooks/analyse.ipynb    # démonstration explicative
results/examples/          # résultats agrégés exploratoires réels (SANS données brutes)
slides/                    # PPTX et PDF de soutenance (chiffres exploratoires)
tests/                     # pytest (non régression, erreurs, calibration)
```

Le vérificateur indépendant n'importe ni le solveur, ni NetworkX, ni le code de sélection : il reconstruit la couverture et le poids coupé à partir des sorties JSON. Il vérifie que les sélections sont de taille **exactement k** et compare à la force brute sur les petits graphes.

## 4. Théorie et méthodes

Pour G=(V,E), on sélectionne `S ⊆ V`, `|S|=k`.

**Objectif obligatoire :** maximiser `f(S)=|∪_{v∈S} ({v} ∪ N(v))|` (couverture des voisinages fermés).

**ILP :** `x_i` indique une personne sélectionnée, `y_j` une personne couverte ; `max Σ y_j`, avec `y_j ≤ Σ_{i∈N[j]} x_i`, `Σ x_i=k`, `x_i∈{0,1}`, `0≤y_j≤1`.

**Glouton :** ajouter à chaque étape la personne au plus grand gain marginal de couverture. Pour ce problème monotone sous-modulaire avec budget cardinal, le score glouton est au moins `1−1/e ≈ 63,2 %` du maximum (borne sur la **couverture**, pas sur les infections).

**Extension pondérée :** maximiser `g(S)=Σ_{e=(u,v)} w_e · 1[u∈S ou v∈S]` ; ILP avec `z_e ≤ x_u+x_v` ; glouton sur les contacts non encore coupés.

| Méthode | Type | Ce qui est optimisé / classé |
|---|---|---|
| `random` | baseline | k personnes tirées au hasard (plusieurs tirages) |
| `degree`, `betweenness`, `pagerank` | centralités | nombre de voisins, intermédiarité, PageRank |
| `closeness`, `kcore`, `strength` | centralités/extension V2 | proximité, k-core, force pondérée |
| `greedy`, `ilp` | méthodes principales | couverture des voisinages |
| `ilp_deg` | extension | couverture optimale puis départage par somme des degrés |
| `greedy_edges`, `ilp_edges` | extension | poids total des contacts coupés |

`optimal=True` signifie que le solveur a **prouvé l'optimum** ; sinon la solution existe mais n'est pas certifiée, avec un repli glouton explicite si le solveur n'en fournit pas. Ne jamais appeler une solution « optimale » si `optimal=False`.

## 5. Installation reproductible

Python 3.11 ou 3.12 conseillé (versions exactes des dépendances testées via Python de l'environnement de vérification).

```bash
cd groupe-b5
python -m venv .venv
# Sous Windows PowerShell : .venv\Scripts\Activate.ps1
# Sous Linux / macOS : source .venv/bin/activate
python -m pip install -r requirements-lock.txt
# Sans exigence de verrouillage strict : python -m pip install -r requirements.txt
```

`.env.example` est présent par conformité aux consignes : **aucun secret ni aucune variable externe n'est nécessaire**. Ni GPU, ni API, ni compte utilisateur.

### Données réelles SocioPatterns

```bash
python data/download_data.py hospital_raw
python data/download_data.py primary_school_raw
```

Si les URL changent ou si le réseau est indisponible, ouvrir les pages listées dans `data/README.md` puis déposer manuellement `hospital.dat.gz` et `primaryschool.csv.gz` dans `data/raw/`. Les données brutes ne sont **pas** présentes dans l'archive finale et ne doivent pas être commitées.

## 6. Utilisation

Depuis la racine `groupe-b5/` :

**A. Démo sans réseau, valable même si les données manquent :**

```bash
python -m src.run_experiments --synthetic --name demo --k 2 4 8 --runs 50 --random-draws 5 --seed-policy fixed
```

**B. Hôpital, transmission uniforme (MVP) :**

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_uniform \
  --k 2 6 10 --runs 55 --random-draws 5 --r0 3 \
  --seed-policy fixed --seed 42 --ilp-time-limit 12
```

**C. Hôpital, transmission pondérée par durée (extension de V2) :**

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_weighted \
  --transmission weighted --target-attack 0.75 --calibration-runs 30 \
  --k 2 6 10 --runs 55 --random-draws 5 \
  --seed-policy fixed --seed 42 --ilp-time-limit 12
```

**D. École primaire, deuxième jeu réel :**

```bash
python -m src.run_experiments --input data/raw/primaryschool.csv.gz --name primary_uniform \
  --k 5 12 --runs 35 --random-draws 5 --r0 3 \
  --seed-policy fixed --seed 42 --ilp-time-limit 8
```

Sous PowerShell, mettre chaque commande sur **une seule ligne** (les `\` de continuation sont prévus pour Linux/macOS). Pour des conclusions finales, augmenter `--runs` à **200–1000** et répéter plusieurs graines.

**Choisir une intervention et sa calibration :** `--transmission uniform` utilise une probabilité `beta` constante ; `--transmission weighted` utilise `p_ij = 1 − exp(-beta × w_ij / moyenne(w))`. `--r0` n'est pertinent que pour le modèle uniforme. Pour le modèle pondéré, utiliser `--target-attack` ou `--beta`. `--seed-policy fixed` garde les mêmes cas initiaux potentiels avant intervention, même s'ils sont ensuite immunisés (sans remplacement). `resample` reproduit le comportement historique de la V1.

**Reproduire les trois scénarios en une commande :** après téléchargement des deux jeux, lancer `python scripts/reproduce_examples.py` (ou `--quick` pour un essai plus court). Les paramètres réels de la commande standard sont ceux des exemples documentés ci-dessus. Une explication de la fusion figure dans `docs/FUSION_V1_V2.md`.

**Sorties par expérience :** `results/<nom>/results.csv`, `config.json` (paramètres, machine, baseline), `solutions/*.json`, 5 graphiques PNG. Le graphe JSON pour vérification est écrit dans `data/processed/<nom>_graph.json`.

## 7. Tests et vérificateur indépendant

```bash
python -m pytest -q
# Exemple après exécution du scénario hôpital :
python -m src.verifier --graph data/processed/hospital_uniform_graph.json \
  --solutions results/hospital_uniform/solutions --strict
```

**Dernière exécution locale lors de la préparation de cette archive : 147 tests réussis, 0 échec.** Les scénarios réels fournis ont également été exécutés et **leurs fichiers de solutions ont été vérifiés en mode strict**. Les tests comprennent : optimum ILP comparé à la force brute sur petits graphes, garantie du glouton, vérification des poids, contraintes k, test de régression SIR uniforme, nouveaux tests de transmission pondérée, reproductibilité, calibration impossible, solveur limité en temps, données absentes/corrompues, réseau indisponible, tests du pipeline et de ses sorties.

Cette sortie est propre à l'environnement de création ; reproduisez-la sur votre ordinateur et gardez la sortie réelle pour la soutenance. Le vérificateur démontre la **faisabilité** et la cohérence des objectifs. Sur un grand graphe il ne recalcule **pas** un optimum exponentiel en temps ; la preuve d'optimalité est le statut du solveur ILP.

## 8. Résultats exploratoires (mesurés sur des données réelles)

Les données sources proviennent des deux archives initiales. Elles ont été utilisées localement, **non ajoutées à la livraison**. Les fichiers `config.json` et `results.csv` dans `results/examples/` donnent tous les détails, et les images peuvent être réutilisées pour l'oral.

| Jeu / scénario | Personnes / contacts distincts | Répétitions SIR par méthode et budget | Budgets k |
|---|---:|---:|---|
| Hôpital, uniforme | 75 / 1 139 | 55 (50 pour les tirages aléatoires) | 2, 6, 10 |
| Hôpital, pondéré | 75 / 1 139 | 55 (50 pour les tirages aléatoires) | 2, 6, 10 |
| École, uniforme | 242 / 8 317 | 35 (50 pour les tirages aléatoires) | 5, 12 |

À l'hôpital avec `k=10`, **taux de réduction moyen relatif** (par rapport au SIR sans intervention dans le même scénario) :

| Méthode | Uniforme | Pondéré |
|---|---:|---:|
| Degré | 45,3 % | 44,4 % |
| Glouton couverture | 40,9 % | 38,6 % |
| ILP couverture (sans départage) | **23,4 %** | **14,4 %** |
| ILP + départage degré | 40,2 % | 39,0 % |
| ILP contacts pondérés | 38,9 % | 46,3 % |

Toutes les sélections ILP de couverture de `k=10` couvrent 100 % des personnes, pourtant elles n'entraînent **pas** le même taux d'attaque en SIR. Cela montre que maximiser la couverture des voisinages **n'est pas identique** à minimiser la taille de l'épidémie. Le scénario pondéré peut reclasser certaines méthodes.

**Lecture de la baseline aléatoire :** les métriques de la ligne `random` du CSV sont des moyennes sur plusieurs sélections ; le fichier `solutions/random_k*.json` enregistre une seule sélection représentative afin de permettre la vérification indépendante de sa faisabilité. Sa couverture n'est donc pas nécessairement égale à la couverture moyenne du CSV. Pour les scénarios fournis, chaque tirage aléatoire possède 10 simulations SIR, soit 50 mesures au total.

**Ces résultats sont illustratifs et exploratoires** : 35/55 répétitions restent insuffisantes pour conclure à quelques points près. Les taux varient avec les graines, le modèle, les paramètres de calibration et le nombre de répétitions. Les temps mesurés ne sont pas transférables à un autre PC. Ne pas comparer directement les réductions des deux scénarios comme si leur `beta` avait la même signification : leurs baselines ont été calibrées différemment.

## 9. Limites et plan B

- Modèle SIR stylisé sans âge, incubation, symptomatologie, sensibilité/spécificité des tests, délai, observance ou validation clinique.
- Graphe statique : perte de l'ordre temporel, pas de contraintes d'horaires ; contacts pondérés = hypothèse de risque approximative.
- Les graphes agrégés ne représentent pas nécessairement une transmission vraie ; `R0` calculé est une approximation structurelle limitée au modèle uniforme.
- Comparaison Monte-Carlo : p-values ou intervalles de différences non calculés ; des écarts faibles peuvent être du bruit.
- ILP NP-difficile en général ; le coût peut exploser sur un graphe plus grand ; limites de temps et repli explicites.
- Sans téléchargement possible : `--synthetic` fonctionne hors ligne avec tous les algorithmes ; les exemples PNG/CSV dans `results/examples/` servent de démonstration enregistrée.
- Échec du solveur, instance infaisable, données absentes et poids invalides sont testés ; pas de dépendance GPU ou API.

## 10. Répartition, organisation Git et soumission

La répartition proposée en §1 doit être validée. Les ZIP fournis ne contiennent **aucun historique de collaboration** ; les vrais commits, branches, auteurs et revues doivent être vérifiés dans votre fork. Faire une PR uniquement vers `jsboigeEPF/2026-MSMIS5IN11-Search-Symbolic:main`, avec **un seul dossier `groupe-b5/`** à la racine. Ne pas supprimer les fichiers du professeur ou d'autres groupes. Utiliser le modèle et la checklist de PR. **Date limite : lundi 23 novembre 2026 à 23h59. Soutenance : mercredi 25 novembre 2026.** Voir `docs/CHECKLIST_AVANT_PR.md` et `docs/PLAN_ORAL.md`.

## 11. Licences et références

- **Code : licence à approuver par les deux membres avant publication.** Proposition MIT documentée dans `docs/LICENCE_CODE_A_VALIDER.md` ; ne pas annoncer cette proposition comme déjà adoptée.
- **Données :** licence et attribution SocioPatterns à vérifier sur la page du jeu exact ; origine, notices et articles dans `data/README.md`. Aucune donnée brute copiée dans l'archive finale.
- **Bibliothèques :** NumPy, SciPy/HiGHS, pandas, NetworkX, Matplotlib, pytest et Notebook, sous leurs licences tierces respectives.
- Kempe, Kleinberg & Tardos (2003), *Maximizing the spread of influence through a social network*, KDD.
- Nemhauser, Wolsey & Fisher (1978), *An analysis of approximations for maximizing submodular set functions*.
- Cours : [Search-09-LinearProgramming](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-09-LinearProgramming.ipynb), [Search-04-LocalSearch](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-04-LocalSearch.ipynb).
- Données : [SocioPatterns](http://www.sociopatterns.org/datasets/), Vanhems et al. (2013) et Stehlé et al. (2011).

**Pour les dernières vérifications**, suivre `docs/CHECKLIST_AVANT_PR.md`. Ne pas supprimer les fichiers de consignes du dépôt amont ni inclure les ZIP sources dans votre fork.
