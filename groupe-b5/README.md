
# B5 — Qui tester en priorité ? Optimisation sur un graphe de contacts

> Projet B5 — IA exploratoire et symbolique, EPF, 2026-2027. Nous comparons plusieurs stratégies de sélection sur des réseaux de contacts SocioPatterns. Les simulations SIR nous servent à évaluer leur effet sur la propagation d’une épidémie.

## 1. Membres du groupe et répartition du travail

| Membre (GitHub) | Travail réalisé | Fichiers principaux |
|---|---|---|
| `asdesasdesas` | Préparation des données SocioPatterns, construction des graphes, simulations SIR uniforme et pondérée, tests du modèle et analyse méthodologique | `src/data.py`, `src/sir.py`, `data/`, `tests/test_sir.py`, `docs/ANALYSE_METHODOLOGIQUE.md` |
| `A03h06A` | Méthodes d’optimisation (glouton, ILP et centralités), vérificateur indépendant, exécution des expériences et génération des graphiques | `src/selection.py`, `src/verifier.py`, `src/run_experiments.py`, `src/plots.py`, `tests/` |
| Travail commun | Relectures, validation des résultats, préparation de la démonstration et de la soutenance | `notebooks/`, `slides/`, `README.md`, `results/examples/` |

Nous avons utilisé des assistants IA, notamment ChatGPT et Claude, afin de nous aider à optimiser et comprendre certaines parties du code, ainsi qu'à améliorer la documentation et à analyser les résultats. Nous avons exécuté les expériences en local et vérifié les sorties avec les tests et le vérificateur du projet.

## 2. Présentation du projet

Notre sujet est le **B5 - « Qui tester en priorité ? »**. Nous cherchons à déterminer quelles personnes cibler sur un réseau de contacts lorsqu’on dispose d’un budget d’intervention limité à `k` personnes.

Nous avons d’abord construit des graphes à partir de deux jeux de données SocioPatterns : un réseau de contacts dans un hôpital et un réseau dans une école primaire. Nous avons ensuite implémenté plusieurs méthodes pour choisir les personnes à immuniser, notamment des méthodes fondées sur les centralités du graphe, un algorithme glouton et une formulation en programmation linéaire en nombres entiers (ILP).

Pour comparer ces sélections, nous avons développé un simulateur épidémiologique SIR et mesuré le taux d’attaque, la couverture du réseau, les contacts coupés et les temps de calcul. Nous avons également ajouté un modèle SIR pondéré par la durée cumulée des contacts, ainsi qu’un second objectif d’optimisation portant sur le poids des contacts coupés.

Nous n’avons pas implémenté de graphe temporel ni de budget d’intervention différent selon les individus.

### Hypothèses médicales

Nous avons fait l’hypothèse que les personnes sélectionnées sont **immédiatement et parfaitement immunisées** (ou isolées de façon parfaite). Notre simulation ne représente donc pas le dépistage seul, car un test n’empêche pas directement une contamination. Il faudrait notamment modéliser les résultats des tests, leur fiabilité et les mesures prises ensuite.

Les résultats sont ceux d’un modèle pédagogique et ne constituent pas une recommandation médicale. Nous détaillons ces choix dans [`docs/ANALYSE_METHODOLOGIQUE.md`](docs/ANALYSE_METHODOLOGIQUE.md).

## 3. Architecture

```text
data/download_data.py       # téléchargement (données exclues du dépôt)
       │
       ▼
src/data.py                 # t, i, j, catégories -> graphe statique pondéré
       │
       ├── src/selection.py # aléatoire, centralités, gloutons, ILP (HiGHS)
       │
       ├── src/sir.py       # évaluation SIR uniforme OU pondérée
       │
       ▼
src/run_experiments.py      # budget k, métriques, CSV, config JSON, PNG
       │
       ├── src/plots.py     # visualisations
       └── src/verifier.py  # contrôle indépendant via JSON (standard library)

notebooks/analyse.ipynb     # démonstration explicative
results/examples/           # résultats expérimentaux réels agrégés (sans données brutes)
slides/                     # supports de soutenance
tests/                      # pytest (non-régression, erreurs, calibration)
```

Le vérificateur indépendant n'importe ni le solveur, ni NetworkX, ni le code de sélection : il reconstruit la couverture et le poids coupé à partir des sorties JSON. Il vérifie que les sélections sont de taille **exactement k** et compare à la force brute sur les petits graphes.

## 4. Méthodes de sélection

Pour un graphe $G=(V,E)$, nous sélectionnons un ensemble de personnes $S \subseteq V$ avec $|S|=k$.

**Objectif principal :** maximiser la couverture des voisinages fermés :

$$
f(S) = \left|\bigcup_{v \in S} \left(\{v\} \cup N(v)\right)\right|
$$

**ILP :** nous utilisons une variable binaire $x_i$ pour indiquer si une personne est sélectionnée et une variable $y_j$ pour indiquer si elle est couverte. La formulation consiste à maximiser :

$$
\sum_{j \in V} y_j
$$

sous les contraintes :

$$
y_j \leq \sum_{i \in N[j]} x_i
$$

$$
\sum_{i \in V} x_i = k
$$

avec $x_i \in \{0,1\}$ et $0 \leq y_j \leq 1$.

**Glouton :** à chaque étape, nous ajoutons la personne qui apporte le plus grand gain marginal de couverture. Pour cet objectif monotone sous-modulaire et une contrainte de cardinalité, l'algorithme glouton garantit au moins $1-1/e \approx 63,2\,\%$ de la valeur optimale. Cette garantie concerne la couverture du réseau et non directement la réduction des infections.

**Objectif complémentaire :** nous cherchons également à maximiser le poids total des contacts coupés :

$$
g(S) = \sum_{e=(u,v)\in E} w_e \cdot \mathbf{1}[u\in S \text{ ou } v\in S]
$$

Pour cet objectif, nous utilisons une formulation ILP avec la contrainte $z_e \leq x_u+x_v$ ainsi qu'un algorithme glouton qui privilégie les contacts pondérés non encore coupés.

| Méthode | Type | Ce qui est optimisé / classé |
|---|---|---|
| `random` | Référence aléatoire | k personnes tirées au hasard |
| `degree`, `betweenness`, `pagerank` | Centralités | Degré, intermédiarité, PageRank |
| `closeness`, `kcore`, `strength` | Centralités | Proximité, k-core, force pondérée |
| `greedy`, `ilp` | Méthodes principales | Couverture des voisinages |
| `ilp_deg` | Méthode complémentaire | Couverture puis départage par degré |
| `greedy_edges`, `ilp_edges` | Méthodes complémentaires | Poids total des contacts coupés |

Pour les méthodes ILP, le statut `optimal=True` indique que le solveur a prouvé l'optimalité pour la fonction objectif considérée. Si aucune solution exploitable n'est trouvée, notre programme utilise un repli glouton.

Une solution optimale pour la couverture n'est pas nécessairement celle qui réduit le plus les infections.

## 5. Installation

Le projet utilise Python 3.11 à 3.13 et les dépendances indiquées dans les fichiers `requirements`.

```bash
cd groupe-b5
python -m venv .venv
# Sous Windows PowerShell : .venv\Scripts\Activate.ps1
# Sous Linux / macOS : source .venv/bin/activate
python -m pip install -r requirements-lock.txt
# Sans exigence de verrouillage strict : python -m pip install -r requirements.txt
```

Le projet fonctionne sans GPU et sans API externe. Nous avons conservé un fichier `.env.example`, mais aucune clé n’est nécessaire.

### Données réelles SocioPatterns

```bash
python data/download_data.py hospital_raw
python data/download_data.py primary_school_raw
```

Si les URL changent ou si le réseau est indisponible, ouvrir les pages listées dans `data/README.md` puis déposer manuellement `hospital.dat.gz` et `primaryschool.csv.gz` dans `data/raw/`.

Les données brutes ne sont **pas** versionnées dans le dépôt.

## 6. Utilisation

Depuis la racine `groupe-b5/` :

**A. Simulation sur un graphe synthétique :**

```bash
python -m src.run_experiments --synthetic --name demo --k 2 4 8 --runs 50 --random-draws 5 --seed-policy fixed
```

**B. Hôpital — SIR uniforme :**

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_uniform_final --k 2 6 10 --runs 200 --random-draws 10 --r0 3 --seed-policy fixed --seed 42 --ilp-time-limit 12
```

**C. Hôpital — SIR pondéré :**

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_weighted_final --transmission weighted --target-attack 0.75 --calibration-runs 100 --k 2 6 10 --runs 200 --random-draws 10 --seed-policy fixed --seed 42 --ilp-time-limit 12
```

**D. École primaire — SIR uniforme :**

```bash
python -m src.run_experiments --input data/raw/primaryschool.csv.gz --name primary_uniform_final --k 5 12 --runs 200 --random-draws 10 --r0 3 --seed-policy fixed --seed 42 --ilp-time-limit 8
```

Nous avons utilisé 200 simulations SIR pour les expériences finales. Les commandes sont écrites sur une ligne pour pouvoir être copiées directement dans PowerShell.

**Paramètres de simulation :** `--transmission uniform` utilise une probabilité `beta` constante ; `--transmission weighted` utilise `p_ij = 1 − exp(-beta × w_ij / moyenne(w))`.

`--r0` n'est pertinent que pour le modèle uniforme. Pour le modèle pondéré, utiliser `--target-attack` ou `--beta`.

`--seed-policy fixed` garde les mêmes cas initiaux potentiels avant intervention, même s'ils sont ensuite immunisés (sans remplacement). `resample` remplace un cas initial qui aurait été immunisé.

Un script supplémentaire, `python scripts/reproduce_examples.py`, permet de lancer les scénarios prédéfinis (`--quick` pour un essai plus court). Les commandes détaillées ci-dessus correspondent aux expériences finales étudiées dans notre analyse.

**Sorties par expérience :** `results/<nom>/results.csv`, `config.json` (paramètres, machine, baseline), `solutions/*.json`, 5 graphiques PNG. Le graphe JSON pour vérification est écrit dans `data/processed/<nom>_graph.json`.

## 7. Tests et vérificateur indépendant

Pour lancer les tests automatisés :

```bash
python -m pytest -q
```

Vérification indépendante des expériences finales, après leur exécution :

**Hôpital — SIR uniforme :**

```bash
python -m src.verifier --graph data/processed/hospital_uniform_final_graph.json --solutions results/hospital_uniform_final/solutions --strict
```

**Hôpital — SIR pondéré :**

```bash
python -m src.verifier --graph data/processed/hospital_weighted_final_graph.json --solutions results/hospital_weighted_final/solutions --strict
```

**École primaire — SIR uniforme :**

```bash
python -m src.verifier --graph data/processed/primary_uniform_final_graph.json --solutions results/primary_uniform_final/solutions --strict
```

**Nous avons obtenu 147 tests automatisés réussis, sans échec.**

Les contrôles indépendants en mode strict ont validé :
- **36/36 solutions** pour l'hôpital avec le SIR uniforme.
- **36/36 solutions** pour l'hôpital avec le SIR pondéré.
- **24/24 solutions** pour l'école primaire avec le SIR uniforme.

Soit **96/96 solutions valides au total**.

Les tests comprennent notamment l'optimum ILP comparé à la force brute sur petits graphes, les contraintes de cardinalité, les modèles SIR, les poids, la reproductibilité et la calibration.

Notre vérificateur contrôle la **faisabilité** des sélections et la cohérence des métriques. Il ne démontre pas l’optimalité des solutions sur les grands graphes : celle-ci dépend du statut retourné par le solveur ILP.

## 8. Résultats expérimentaux (données réelles)

Nous avons téléchargé et utilisé les données SocioPatterns en local, sans les ajouter au dépôt.

Les résultats des trois expériences finales sont conservés dans les dossiers suivants :

- `results/examples/hospital_uniform_final/`
- `results/examples/hospital_weighted_final/`
- `results/examples/primary_uniform_final/`

Chaque dossier contient les résultats numériques, les paramètres de simulation, les graphiques et les solutions des méthodes testées.

Le détail des analyses, des intervalles de confiance et des limites se trouve dans [`docs/ANALYSE_METHODOLOGIQUE.md`](docs/ANALYSE_METHODOLOGIQUE.md).


| Jeu / scénario | Personnes / arêtes | Répétitions SIR | Budgets k |
|---|---|---|---|
| Hôpital, uniforme final | 75 / 1 139 | 200 par sélection évaluée ; 10 tirages aléatoires | 2, 6, 10 |
| Hôpital, pondéré final | 75 / 1 139 | 200 par sélection évaluée ; 10 tirages aléatoires | 2, 6, 10 |
| École, uniforme final | 242 / 8 317 | 200 par sélection évaluée ; 10 tirages aléatoires | 5, 12 |

**Paramètres des expériences hospitalières :** en uniforme, `beta = 0,01744`, `gamma = 0,2`, `R0` cible de 3 et taux d'attaque **sans intervention de 81,5 %**.

En pondéré, `beta = 0,03162`, `gamma = 0,2`, cible de calibration de 75 % (75,5 % obtenu à la calibration) et taux d'attaque de référence final de **73,1 %**.

### Comparaison sur l'hôpital pour k = 10

| Méthode | Taux d'attaque uniforme | Taux d'attaque pondéré | Réduction relative uniforme | Réduction relative pondérée |
|---|---:|---:|---:|---:|
| `random` | 64,1 % | 57,7 % | 21,4 % | 21,0 % |
| `degree` | **41,9 %** | 38,2 % | **48,6 %** | 47,8 % |
| `betweenness` | 44,8 % | 40,2 % | 45,0 % | 45,0 % |
| `pagerank` | **41,9 %** | 38,2 % | **48,6 %** | 47,8 % |
| `closeness` | **41,9 %** | 38,2 % | **48,6 %** | 47,8 % |
| `kcore` | 46,4 % | **32,8 %** | 43,1 % | **55,2 %** |
| `strength` | 46,4 % | **32,8 %** | 43,1 % | **55,2 %** |
| `greedy` | 46,4 % | 39,8 % | 43,1 % | 45,6 % |
| `ilp` | 63,9 % | 60,5 % | 21,6 % | 17,2 % |
| `ilp_deg` | 45,2 % | 39,5 % | 44,6 % | 45,9 % |
| `greedy_edges` | 46,4 % | **32,8 %** | 43,1 % | **55,2 %** |
| `ilp_edges` | 46,4 % | **32,8 %** | 43,1 % | **55,2 %** |

*Le taux d'attaque est la fraction moyenne de la population infectée au cours des simulations. Plus il est faible, mieux c'est. La réduction relative est calculée par rapport à la référence propre à chaque scénario.*

Pour `k = 10`, `degree`, `pagerank` et `closeness` obtiennent les plus faibles moyennes en **uniforme** (41,9 %), tandis que `kcore`, `strength`, `greedy_edges` et `ilp_edges` obtiennent les plus faibles moyennes en **pondéré** (32,8 %).

Le classement observé dépend donc du modèle de transmission.

**Lien entre couverture et propagation :** `ilp` couvre les 75 personnes pour `k = 10` dans les deux scénarios, mais son taux d'attaque reste de 63,9 % en uniforme et de 60,5 % en pondéré. Des ensembles ayant la même couverture peuvent avoir des effets épidémiques différents.

**Temps de calcul :** pour `k = 10` en pondéré, `greedy_edges` et `ilp_edges` ont le même taux d'attaque moyen (32,8 %), avec des temps de sélection d'environ 0,0070 s et 0,0475 s lors de la dernière exécution. Ces temps dépendent de la machine et ne constituent pas un benchmark répété.

**Variabilité des simulations :** dans le scénario uniforme (`k = 10`), l'IC 95 % du taux d'attaque de `degree` est d'environ [38,7 % ; 45,2 %] contre [61,8 % ; 66,4 %] pour `random`. En pondéré, l'IC de `strength` est d'environ [29,9 % ; 35,6 %] contre [55,3 % ; 60,1 %] pour `random`.

Le chevauchement d'autres intervalles ne suffit pas à départager les méthodes proches ; des comparaisons appariées seraient utiles.

**Sélection aléatoire :** les métriques de `random` agrègent plusieurs sélections ; le fichier `solutions/random_k*.json` contient une sélection représentative pour contrôler sa faisabilité, et sa couverture peut donc différer de la moyenne affichée dans le CSV.

**Comparaison des modèles :** les deux scénarios ont été calibrés différemment et n’ont pas le même taux d’attaque sans intervention. Le classement des méthodes s’interprète donc principalement **à l’intérieur de chaque scénario**.

Les résultats relèvent d’une simulation pédagogique avec immunisation parfaite, et non d’un modèle clinique de dépistage.

### Résultats sur l'école primaire

Nous avons également testé les méthodes sur le réseau de l'école primaire, composé de **242 personnes et 8 317 arêtes**.

Cette expérience utilise le SIR uniforme, avec `beta = 0,00794`, `gamma = 0,2` et un `R0` cible de 3.

Le taux d'attaque moyen sans intervention est de **83,2 %**.

Nous avons testé deux budgets d'immunisation, `k = 5` et `k = 12`, avec 200 simulations SIR par sélection évaluée.

Pour `k = 12`, les résultats principaux sont :

| Méthode | Couverture | Taux d'attaque | Réduction relative |
|---|---:|---:|---:|
| `random` | 227,5 / 242 | 78,7 % | 5,4 % |
| `degree` | 228 / 242 | 74,8 % | 10,1 % |
| `betweenness` | 232 / 242 | 72,5 % | 12,9 % |
| `greedy` | 242 / 242 | 72,9 % | 12,4 % |
| `ilp` | 242 / 242 | 74,7 % | 10,2 % |
| `ilp_deg` | 242 / 242 | **71,6 %** | **14,0 %** |

Pour `k = 12`, `greedy`, `ilp` et `ilp_deg` atteignent tous une couverture totale des 242 personnes. Cependant, leurs taux d'attaque sont différents.

La méthode `ilp_deg` obtient le taux d'attaque moyen le plus faible parmi les méthodes testées, avec 71,6 %, contre 72,9 % pour `greedy` et 74,7 % pour `ilp`.

Ce résultat montre qu'une couverture maximale du réseau ne suffit pas à garantir la meilleure réduction des infections.

Il faut toutefois rester prudent sur les écarts faibles entre les méthodes, car les résultats dépendent des simulations SIR.

## 9. Limites du projet

- Modèle SIR stylisé sans âge, incubation, symptomatologie, sensibilité/spécificité des tests, délai, observance ou validation clinique.

- Graphe statique : perte de l'ordre temporel, pas de contraintes d'horaires ; contacts pondérés = hypothèse de risque approximative.

- Les graphes agrégés ne représentent pas nécessairement une transmission vraie ; `R0` calculé est une approximation structurelle limitée au modèle uniforme.

- Comparaison Monte-Carlo : p-values ou intervalles de différences non calculés ; des écarts faibles peuvent être du bruit.

- ILP NP-difficile en général ; le coût peut exploser sur un graphe plus grand ; limites de temps et repli explicites.

- La simulation sur graphe synthétique permet de présenter le fonctionnement du programme sans avoir besoin de télécharger les données.

- Nous avons testé plusieurs cas d’erreur, notamment les données absentes ou invalides et les limites du solveur.

## 10. Bilan

Nos expériences montrent qu’une sélection fondée sur la structure du réseau peut réduire davantage la propagation simulée qu’une sélection aléatoire.

Nous avons aussi observé que les méthodes les plus efficaces ne sont pas forcément les mêmes avec un modèle SIR uniforme et un modèle pondéré.

Enfin, une solution optimale pour la couverture des voisinages ne garantit pas le meilleur résultat épidémiologique. Cette observation se retrouve aussi sur le réseau de l'école primaire, où plusieurs méthodes obtiennent une couverture totale sans produire exactement le même taux d'attaque.

Ces constats restent limités aux jeux de données et aux hypothèses étudiés. Le détail des résultats et des limites figure dans notre analyse méthodologique.

## 11. Sources et références

- **Données :** les jeux de contacts proviennent de SocioPatterns ; les références et les indications de téléchargement sont regroupées dans `data/README.md`. Les données brutes ne sont pas redistribuées dans le dépôt.

- **Dépendances :** NumPy, SciPy/HiGHS, pandas, NetworkX, Matplotlib, pytest et Notebook, sous leurs licences tierces respectives.

- Kempe, Kleinberg & Tardos (2003), **Maximizing the spread of influence through a social network**, KDD.

- Nemhauser, Wolsey & Fisher (1978), **An analysis of approximations for maximizing submodular set functions**.

- Cours : [Search-09-LinearProgramming](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-09-LinearProgramming.ipynb), [Search-04-LocalSearch](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/Search/Part1-Foundations/Search-04-LocalSearch.ipynb).

- Données : [SocioPatterns](http://www.sociopatterns.org/datasets/), Vanhems et al. (2013) et Stehlé et al. (2011).
