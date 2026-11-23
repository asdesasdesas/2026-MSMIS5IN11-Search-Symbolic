# Méthodologie et limites du projet B5

## 1. Objectifs d'optimisation

L'objectif du projet est de déterminer quelles personnes cibler en priorité sur un réseau de contacts, avec un budget d'intervention limité, afin de réduire la propagation d'une épidémie.

Pour un graphe G = (V, E), on cherche à sélectionner exactement k nœuds formant un ensemble S.

Deux objectifs d'optimisation sont étudiés :

- **Couverture des voisinages** :

$$
f(S) = \left|\bigcup_{v \in S} \left(\{v\} \cup N(v)\right)\right|
$$

L'objectif est de maximiser le nombre de personnes couvertes. Une personne est considérée comme couverte si elle est sélectionnée ou si elle est voisine d'au moins une personne sélectionnée.

- **Contacts coupés pondérés** :

$$
g(S) = \sum_{e=(u,v)\in E} w_e \cdot \mathbf{1}[u\in S \text{ ou } v\in S]
$$

L'objectif est de maximiser le poids total des contacts neutralisés par la sélection. Chaque arête est comptée une seule fois, même si ses deux extrémités sont sélectionnées.

### Formulation ILP

Pour la couverture des voisinages :

- x_v ∈ {0,1} : indique si le nœud v est sélectionné ;
- y_u ∈ [0,1] : indique si le nœud u est couvert ;
- objectif : maximiser ∑ y_u ;
- contraintes :

$$
y_u \leq \sum_{v \in N[u]} x_v
$$

$$
\sum_{v \in V} x_v = k
$$

Pour les contacts coupés pondérés :

- x_v ∈ {0,1} : indique si le nœud v est sélectionné ;
- z_e ∈ [0,1] : indique si l'arête e est neutralisée ;
- objectif : maximiser ∑ w_e z_e ;
- contraintes :

$$
z_e \leq x_u + x_v \quad \forall e=(u,v)\in E
$$

$$
\sum_{v \in V} x_v = k
$$

Les variables auxiliaires peuvent être continues, car leurs coefficients dans la fonction objectif sont non négatifs et la maximisation permet d'atteindre la valeur 1 lorsqu'un élément est couvert.

### Propriétés de l'algorithme glouton

Les deux fonctions objectifs sont **monotones et sous-modulaires**.

Cela signifie que l'ajout d'un nœud à une sélection ne diminue pas la valeur de l'objectif, mais que son apport supplémentaire tend à diminuer lorsque la sélection s'agrandit.

Pour ces fonctions et sous une contrainte de cardinalité k, l'algorithme glouton garantit au moins 1 - 1/e ≈ 63,2 % de la valeur optimale.

Cette garantie concerne uniquement **l'objectif d'optimisation combinatoire**, et non directement la réduction du nombre de personnes infectées dans la simulation SIR.

### Gestion de l'optimalité

L'ILP renvoie `optimal=True` uniquement lorsque le solveur HiGHS a prouvé l'optimalité de la solution.

Si le solveur ne trouve aucune solution exploitable, un repli vers l'algorithme glouton est prévu et signalé.

Pour l'ILP avec départage par degré, l'optimalité du départage n'est validée qu'après preuve d'optimalité de la seconde étape.

## 2. Hypothèses médicales

Dans notre modèle, les personnes sélectionnées bénéficient d'une **immunisation parfaite et immédiate**.

Elles ne peuvent donc plus être infectées ni transmettre la maladie. Cela revient également à neutraliser leurs contacts du point de vue de la transmission.

Cette hypothèse correspond à un scénario idéalisé de vaccination parfaitement efficace ou d'isolement complet, et non à un simple dépistage.

En effet, un test de dépistage ne permet pas directement d'empêcher une contamination. Pour représenter une véritable stratégie de dépistage, il faudrait notamment prendre en compte :

- la sensibilité et la spécificité des tests ;
- le délai d'obtention des résultats ;
- l'isolement des personnes positives ;
- l'observance des mesures d'isolement ;
- le risque de faux négatifs.

Ces éléments ne sont pas modélisés dans le MVP.

Notre projet constitue donc un **modèle pédagogique d'aide à la sélection**, et non une recommandation clinique ou un outil de tri utilisable directement dans un établissement de santé.

## 3. Modèles de simulation SIR

Le modèle SIR permet d'évaluer les sélections obtenues par les différents algorithmes d'optimisation.

Chaque personne peut se trouver dans l'un des états suivants :

- S (Susceptible) : personne susceptible d'être infectée ;
- I (Infectious) : personne infectée et contagieuse ;
- R (Recovered) : personne guérie ou retirée de la transmission ;
- IMMUNE : personne immunisée par l'intervention.

À chaque pas de simulation, les personnes infectées peuvent transmettre la maladie à leurs voisins susceptibles, puis guérir selon une probabilité gamma.

Les nouvelles contaminations deviennent contagieuses au pas suivant.

### 3.1. SIR uniforme

Dans le modèle `uniform`, toutes les arêtes possèdent la même probabilité de transmission beta à chaque pas de simulation.

La durée cumulée des contacts n'intervient donc pas directement dans la probabilité de transmission.

Le paramètre beta est calibré à partir des caractéristiques du graphe, de la probabilité de guérison gamma et d'un nombre de reproduction de base R0 cible.

Dans nos expériences principales, le scénario uniforme utilise un R0 cible de 3 et une probabilité de guérison gamma de 0,2.

Une valeur de gamma égale à 0,2 correspond à une probabilité de guérison de 20 % à chaque pas, soit une durée infectieuse moyenne de cinq pas de simulation.

Ces pas ne correspondent pas nécessairement à une durée médicale réelle, comme une journée.

### 3.2. SIR pondéré

Dans le modèle `weighted`, la probabilité de transmission dépend du poids de chaque arête :

$$
p_{ij} = 1 - e^{-\beta \frac{w_{ij}}{\overline{w}}}
$$

avec :

- beta : paramètre global de transmission ;
- w_ij : poids du contact entre les personnes i et j ;
- moyenne(w) : poids moyen des arêtes du graphe ;
- p_ij : probabilité de transmission associée à cette arête.

Une durée cumulée de contact plus importante entraîne donc une probabilité de transmission plus élevée dans le modèle.

Cette relation constitue une **hypothèse de modélisation** et non un étalonnage clinique validé.

### 3.3. Calibration des paramètres

L'approximation de R0 utilisée dans le modèle uniforme ne s'applique pas directement au modèle pondéré.

Pour le scénario pondéré, il est possible d'utiliser :

- `--target-attack` : calibration de beta par simulations
  Monte-Carlo afin d'atteindre un taux d'attaque cible sans intervention ;
- `--beta` : utilisation d'une valeur de beta fixée directement,
  en documentant le taux d'attaque obtenu sans intervention.

La calibration est approximative et peut ne pas atteindre la cible. Le programme signale cette situation.

Les deux modèles ne sont donc pas nécessairement calibrés au même niveau de propagation initiale. Leurs résultats doivent être comparés en tenant compte de cette différence.

### 3.4. Sélection des cas initiaux

Deux stratégies de sélection des cas initiaux sont disponibles :

- `seed-policy fixed` : les mêmes candidats à l'infection initiale
  sont utilisés pour comparer les méthodes. Si une personne ciblée par l'intervention fait partie de ces candidats, elle ne devient pas infectieuse et n'est pas remplacée.

- `seed-policy resample` : lorsqu'un candidat initial est immunisé,
  il est remplacé par une personne non immunisée.

La stratégie `fixed` permet de comparer les interventions à partir des mêmes candidats initiaux et de prendre en compte la prévention des infections initiales.

La répétition des simulations permet de limiter l'influence des tirages aléatoires sur les résultats.

## 4. Protocole de comparaison équitable

Afin de comparer les différentes méthodes de sélection dans des conditions similaires, le protocole suivant est utilisé :

1. Utiliser le même graphe agrégé, le même seuil de filtrage et
   le même budget k pour toutes les méthodes d'une expérience.

2. Conserver les mêmes paramètres épidémiques beta et gamma
   pour comparer les interventions au sein d'une même expérience.

3. Utiliser des graines aléatoires contrôlées afin de permettre
   la reproduction des simulations.

4. Comparer les algorithmes d'optimisation à des méthodes de
   référence simples : sélection aléatoire, centralité degré et absence d'intervention.

5. Mesurer plusieurs indicateurs :
   - couverture des voisinages ;
   - poids des contacts coupés ;
   - temps de calcul de la sélection ;
   - taux d'attaque moyen et médian ;
   - dispersion des résultats ;
   - probabilité d'épidémie majeure ;
   - réduction de la propagation par rapport à l'absence
     d'intervention.

6. Vérifier les solutions à l'aide du vérificateur indépendant.
   Celui-ci contrôle notamment les contraintes de sélection et recalcule les métriques annoncées. Pour les petits graphes, une comparaison par force brute peut également être réalisée.

7. Indiquer qu'une solution est optimale uniquement lorsque
   son optimalité a été prouvée.

8. Augmenter le nombre de répétitions des simulations
   (200 répétitions ont été utilisées pour les expériences finales sur les réseaux hospitalier et scolaire), et, si possible, étudier la sensibilité aux paramètres beta, gamma et aux graines aléatoires.

Il est essentiel de distinguer **la qualité de l'optimisation combinatoire** de **la performance épidémiologique**.

Une solution optimale pour la couverture des voisinages ne garantit pas nécessairement le taux d'attaque le plus faible.

## 5. Influence du seuil de contacts sur la construction du graphe

### 5.1. Principe

Les données SocioPatterns enregistrent les contacts entre deux personnes par intervalles de 20 secondes.

Lors de la construction du graphe statique :

- un nœud représente une personne ;
- une arête représente une relation de contact ;
- le poids d'une arête correspond au nombre d'intervalles de
  contact enregistrés entre les deux personnes.

Le paramètre `min_contacts` correspond au poids minimal nécessaire pour conserver une arête dans le graphe.

Par exemple, un seuil de 2 permet de conserver uniquement les relations de contact dont la durée cumulée est supérieure ou égale à 40 secondes.

Afin d'étudier l'influence du prétraitement des données sur la structure du réseau hospitalier, nous avons testé plusieurs valeurs de ce paramètre.

### 5.2. Résultats obtenus

| Seuil | Durée cumulée minimale | Nœuds | Arêtes | Nœuds isolés | Densité |
|---|---|---|---|---|---|
| 1 | 20 s | 75 | 1139 | 0 | 0,4105 |
| 2 | 40 s | 75 | 976 | 0 | 0,3517 |
| 5 | 100 s | 75 | 722 | 2 | 0,2602 |
| 10 | 200 s | 75 | 505 | 3 | 0,1820 |

La densité représente la proportion d'arêtes présentes dans le graphe par rapport au nombre maximal d'arêtes possibles.

Pour un graphe non orienté sans boucle, elle est calculée par :

Densité = 2E / (N × (N - 1))

avec N le nombre de nœuds et E le nombre d'arêtes.

### 5.3. Analyse des résultats

On observe que lorsque le seuil augmente, le nombre d'arêtes et la densité du graphe diminuent, tandis que le nombre de nœuds reste constant.

Entre les seuils 1 et 10, le nombre d'arêtes passe de 1139 à 505, soit une diminution d'environ 55,7 %.

La densité du réseau passe également de 41,05 % à 18,20 %.

Pour les seuils de 5 et 10, certains individus deviennent isolés, car aucun de leurs contacts ne possède un poids suffisant pour être conservé dans le graphe.

Le choix du seuil peut donc influencer :

- la structure et la densité du réseau ;
- le nombre de voisins de chaque individu ;
- les mesures de centralité ;
- les personnes sélectionnées par les algorithmes ;
- la calibration du paramètre beta ;
- les résultats des simulations épidémiques.

Cependant, une diminution du nombre d'arêtes ne garantit pas nécessairement une réduction du taux d'attaque, notamment si beta est recalibré pour conserver le même R0 cible.

Cette expérience étudie uniquement l'influence du seuil sur la structure du graphe. Elle ne mesure pas directement son influence sur les résultats SIR.

### 5.4. Justification du seuil retenu

Pour nos expériences principales, nous conservons un seuil `min_contacts = 1` afin de ne pas négliger les contacts de courte durée.

Le modèle SIR pondéré permet ensuite de différencier les probabilités de transmission selon la durée cumulée des contacts.

Ce choix permet de conserver l'ensemble des relations de contact enregistrées, tout en étudiant l'influence de leur durée dans le scénario pondéré.

### 5.5. Reproduction de l'expérience

Depuis le dossier `groupe-b5`, après installation des dépendances et activation de l'environnement Python, télécharger les données hospitalières :

```bash
python data/download_data.py hospital_raw
```

Puis exécuter la commande suivante :

```bash
python -c "from src.data import load_graph; import networkx as nx; [print('Seuil :', s, '| Noeuds :', G.number_of_nodes(), '| Aretes :', G.number_of_edges(), '| Isoles :', nx.number_of_isolates(G), '| Densite :', round(nx.density(G),4)) for s in [1,2,5,10] for G in [load_graph('data/raw/hospital.dat.gz',min_contacts=s)]]"
```

Les données téléchargées restent dans le dossier `data/raw/` et ne sont pas versionnées sur GitHub.

## 6. Validation du modèle SIR

### 6.1. Objectif de la validation

Afin de vérifier le fonctionnement du modèle SIR avant de lancer les expériences sur les données réelles, nous avons réalisé plusieurs tests sur des graphes simples dont le comportement attendu est connu.

Ces vérifications permettent de compléter les tests automatisés du projet et de mieux comprendre l'influence des différents paramètres sur la propagation de l'épidémie.

Les 147 tests automatisés du projet ont également été exécutés avec succès après l'ajout de commentaires dans le fichier `sir.py`.

### 6.2. Vérification de la transmission et de l'immunisation

Les trois premiers tests sont réalisés sur un graphe en chaîne de cinq personnes, avec un seul cas initial, le modèle uniforme, la politique `resample`, une probabilité de guérison gamma = 1 et une graine aléatoire de 42.

| Test | Beta | Personnes immunisées | Taux attendu | Taux obtenu |
|---|---|---|---|---|
| Absence de transmission | 0 | Aucune | 20 % | 20 % |
| Transmission maximale | 1 | Aucune | 100 % | 100 % |
| Immunisation du nœud central | 1 | Nœud 2 | 40 % | 40 % |

Lorsque beta = 0, aucune nouvelle contamination ne se produit. Le taux d'attaque de 20 % correspond uniquement à la personne infectée initialement.

Lorsque beta = 1, dans le modèle uniforme, l'épidémie atteint l'ensemble des personnes du graphe connecté en l'absence d'intervention.

Enfin, lorsque le nœud central est immunisé, la propagation est bloquée entre les deux parties du graphe. Seules deux personnes sur cinq sont infectées.

Ces résultats illustrent l'intérêt d'une sélection stratégique des individus pour interrompre les chaînes de transmission.

### 6.3. Vérification des politiques d'infection initiale

Afin de vérifier la différence entre les politiques `fixed` et `resample`, nous avons utilisé un graphe de cinq personnes avec les paramètres suivants :

- beta = 0 ;
- gamma = 1 ;
- un seul candidat à l'infection initiale ;
- graine aléatoire de 42.

Le premier candidat à l'infection initiale est le nœud 4. Cette personne est volontairement immunisée avant la simulation.

| Politique | Taux attendu | Taux obtenu |
|---|---|---|
| fixed | 0 % | 0 % |
| resample | 20 % | 20 % |

Avec la politique `fixed`, la personne immunisée n'est pas remplacée et l'épidémie ne démarre pas.

Avec la politique `resample`, une autre personne non immunisée est choisie comme cas initial, ce qui explique le taux d'attaque de 20 %.

La politique `fixed` est retenue pour nos expériences principales afin de conserver les mêmes candidats à l'infection initiale entre les différentes stratégies de sélection.

Elle permet également de prendre en compte la prévention des infections initiales par l'intervention.

### 6.4. Vérification du modèle SIR pondéré

Nous avons construit deux graphes en chaîne de trois personnes, possédant la même structure mais des poids différents :

- Graphe A : deux arêtes de poids 10 et 10.
- Graphe B : deux arêtes de poids 1 et 19.

Les deux graphes possèdent le même poids moyen, égal à 10.

Pour chaque configuration, nous avons réalisé 1000 simulations avec beta = 0,5, gamma = 1, un infecté initial, aucune personne immunisée, la politique `resample` et une graine aléatoire de départ de 42.

| Modèle | Graphe A | Graphe B |
|---|---|---|
| Uniforme | 59,57 % | 59,57 % |
| Pondéré | 53,37 % | 49,33 % |

Dans le modèle uniforme, les résultats sont identiques puisque les poids des arêtes ne sont pas pris en compte.

Dans le modèle pondéré, les taux d'attaque moyens diffèrent de 4,04 points de pourcentage.

Dans le graphe B, le contact de poids élevé facilite la transmission entre deux personnes, tandis que le contact de faible poids limite la propagation vers la troisième.

Cette expérience montre que la répartition des poids influence la propagation simulée, même lorsque la structure du graphe et le poids moyen restent identiques.

Cependant, ces résultats ne permettent pas de conclure que le modèle pondéré produit systématiquement moins de contaminations que le modèle uniforme. Le paramètre beta n'a pas exactement la même signification dans les deux modèles.

### 6.5. Vérification de la calibration de R0

La cohérence des fonctions `beta_for_r0()` et `estimate_r0()` a été vérifiée sur le graphe hospitalier, constitué de 75 nœuds et 1139 arêtes, avec un seuil de contacts égal à 1.

| Paramètre | Valeur |
|---|---|
| R0 cible | 3 |
| Gamma | 0,2 |
| Beta calculé | 0,01744284 |
| Transmissibilité T | 0,08152602 |
| R0 estimé | 3,0 |

La valeur de beta obtenue correspond à une probabilité de transmission d'environ 1,74 % par voisin susceptible et par pas de simulation dans le modèle uniforme.

La transmissibilité T correspond à une probabilité d'environ 8,15 % de contaminer un voisin susceptible au cours de la période infectieuse, en considérant la transmission par cette arête.

Le calcul inverse permet de retrouver exactement le R0 cible.

Cette vérification confirme la cohérence mathématique des deux fonctions. Elle ne constitue cependant pas une validation clinique de R0, puisque la formule utilisée reste approximative.

### 6.6. Vérification de la calibration du taux d'attaque

Pour le modèle pondéré, nous avons vérifié la fonction `calibrate_beta_for_attack()` sur le graphe hospitalier.

L'objectif est d'obtenir un taux d'attaque moyen proche de 75 % en l'absence d'intervention.

Les paramètres utilisés sont les suivants :

- gamma = 0,2 ;
- trois candidats à l'infection initiale ;
- aucune personne immunisée ;
- 100 simulations par valeur de beta testée ;
- 12 itérations de dichotomie ;
- politique d'infection initiale `fixed` ;
- graine aléatoire de départ de 999.

| Indicateur | Valeur |
|---|---|
| Beta calibré | 0,03112793 |
| Taux d'attaque cible | 75,00 % |
| Taux d'attaque obtenu | 74,35 % |
| Écart absolu | 0,65 point |
| Objectif atteint | True |

L'écart obtenu est inférieur à la tolérance de cinq points de pourcentage définie dans le programme.

La calibration est donc considérée comme réussie pour les paramètres et l'échantillon de simulations utilisés.

Cette calibration reste une approximation fondée sur des simulations Monte-Carlo. Le taux d'attaque obtenu peut varier avec le nombre de simulations et les graines aléatoires.

### 6.7. Bilan de la validation

Les sept vérifications pratiques ont produit des résultats cohérents avec les comportements attendus.

Elles ont notamment permis de vérifier :

- les cas extrêmes de transmission ;
- le blocage de la propagation par immunisation ;
- les politiques de sélection des cas initiaux ;
- l'influence des poids sur les simulations ;
- la cohérence de la calibration de R0 ;
- la calibration du taux d'attaque du modèle pondéré.

Ces vérifications permettent de poursuivre les expériences sur les données hospitalières avec davantage de confiance dans le fonctionnement du modèle.

Elles constituent une validation fonctionnelle et numérique, et non une validation clinique du modèle épidémiologique.

## 7. Résultats expérimentaux et analyse comparative

Le dossier `results/examples/` contient les résultats finaux de nos trois expériences sur les données SocioPatterns, sans inclure les fichiers de données brutes dans le dépôt.

Les expériences retenues sont :
- l'hôpital avec le modèle SIR uniforme ;
- l'hôpital avec le modèle SIR pondéré ;
- l'école primaire avec le modèle SIR uniforme.


Les paramètres exacts de chaque expérience sont enregistrés dans les fichiers `config.json`.

Les fichiers `results.csv` contiennent les mesures obtenues pour chaque méthode et chaque budget d'intervention.

Les graphiques permettent notamment de comparer :

- l'évolution du taux d'attaque selon le budget k ;
- la probabilité d'épidémie majeure ;
- la relation entre les objectifs d'optimisation et le taux
  d'attaque ;
- le temps de calcul des méthodes ;
- le compromis entre la qualité des solutions et le temps
  de calcul.

Pour les trois expériences finales, nous avons réalisé 200 simulations SIR par sélection évaluée.

La méthode aléatoire utilise également 10 tirages de sélections différentes afin de prendre en compte la variabilité liée au choix des personnes à immuniser.

Ces répétitions permettent de mieux évaluer les performances des différentes méthodes, même si les résultats restent dépendants des paramètres du modèle et des tirages aléatoires.

### 7.1. Résultats sur l'école primaire (protocole final)

L'expérience sur l'école primaire utilise 242 personnes et 8 317 arêtes, le modèle SIR uniforme (R0 cible de 3, gamma = 0,2), la politique `fixed`, une graine de 42 et 200 simulations par sélection évaluée. Les budgets testés sont k = 5 et k = 12, avec une limite de 8 secondes pour l'ILP. Le taux d'attaque moyen sans intervention est de 83,2 %.

**Qualité et temps de calcul.** Pour k = 12, le glouton et l'ILP couvrent tous les deux les 242 personnes, avec des temps de sélection respectifs d'environ 0,020 s et 0,041 s lors de cette exécution. Pour k = 5, l'ILP couvre 236 personnes contre 231 pour le glouton, mais demande environ 4,20 s contre 0,008 s. Les temps dépendent de la machine et ne constituent pas un benchmark répété.

**Couverture et propagation.** Pour k = 12, le glouton, l'ILP et `ilp_deg` atteignent tous une couverture de 242 personnes. Pourtant, les taux d'attaque moyens sont respectivement de 72,9 %, 74,7 % et 71,6 %. `Betweenness` couvre 232 personnes et obtient un taux d'attaque moyen de 72,5 %. La couverture maximale n'entraîne donc pas nécessairement la meilleure réduction des infections.

**Précautions.** Les différences de quelques points entre méthodes ne suffisent pas à établir un classement statistique définitif. Les résultats portent sur un seul réseau, avec une graine contrôlée. Le fichier scolaire a été récupéré manuellement après l'échec du téléchargement automatique.

### 7.2. Résultats sur le réseau hospitalier (protocole final)

Afin de comparer les méthodes de sélection sur le réseau hospitalier SocioPatterns, nous avons réalisé deux expériences : une avec le modèle SIR uniforme et une avec le modèle SIR pondéré.

Le graphe comporte **75 personnes et 1139 arêtes**, avec un seuil `min_contacts = 1`. Les expériences utilisent trois budgets d'immunisation (k = 2, 6 et 10), 200 répétitions SIR par sélection évaluée, 10 tirages pour la méthode aléatoire, une politique d'infection initiale `fixed`, une graine aléatoire de 42 et une limite de résolution ILP de 12 secondes.

Pour le modèle uniforme, le paramètre beta est calibré à partir d'un R0 cible de 3, avec gamma = 0,2. Pour le modèle pondéré, beta est calibré par simulations Monte-Carlo afin d'approcher un taux d'attaque de 75 % sans intervention, avec gamma = 0,2 et 100 simulations par étape de calibration.

Les paramètres complets et les résultats sont disponibles dans `results/examples/hospital_uniform_final/` et `results/examples/hospital_weighted_final/`.

**Résultats du modèle SIR uniforme.**

Le modèle uniforme utilise un beta de 0,01744. Le taux d'attaque moyen sans intervention est de 81,5 %.

| Méthode | k = 2 | k = 6 | k = 10 |
|---|---:|---:|---:|
| Random | 78,5 % | 70,1 % | 64,1 % |
| Degree | 75,2 % | 58,2 % | 41,9 % |
| Betweenness | 75,2 % | 60,1 % | 44,8 % |
| PageRank | 75,2 % | 58,2 % | 41,9 % |
| Closeness | 75,2 % | 58,2 % | 41,9 % |
| K-core | 74,8 % | 61,3 % | 46,4 % |
| Strength | 74,8 % | 61,3 % | 46,4 % |
| Greedy | 75,2 % | 62,1 % | 46,4 % |
| ILP | 75,2 % | 65,9 % | 63,9 % |
| ILP_deg | 75,2 % | 60,3 % | 45,2 % |
| Greedy_edges | 76,8 % | 63,0 % | 46,4 % |
| ILP_edges | 76,8 % | 63,0 % | 46,4 % |

**Valeurs : taux d'attaque moyen. Une valeur faible correspond à moins de personnes infectées.**

Pour k = 10, les méthodes Degree, PageRank et Closeness obtiennent les taux d'attaque les plus faibles (41,9 %), contre 64,1 % pour la sélection aléatoire. Cela correspond à une réduction relative de 48,6 % par rapport à l'absence d'intervention.

Pour ce budget, l'intervalle de confiance à 95 % de Degree est d'environ [38,7 % ; 45,2 %], contre [61,8 % ; 66,4 %] pour Random. L'écart entre ces méthodes est donc important au regard de l'incertitude estimée.

**Résultats du modèle SIR pondéré.**

La calibration du modèle pondéré a conduit à beta = 0,03162. Le taux d'attaque obtenu pendant la calibration est de 75,5 %, pour une cible de 75 %. Lors de l'évaluation finale, le taux d'attaque moyen sans intervention est de 73,1 %.

| Méthode | k = 2 | k = 6 | k = 10 |
|---|---:|---:|---:|
| Random | 70,7 % | 66,5 % | 57,7 % |
| Degree | 69,0 % | 54,3 % | 38,2 % |
| Betweenness | 69,0 % | 55,0 % | 40,2 % |
| PageRank | 69,0 % | 54,3 % | 38,2 % |
| Closeness | 69,0 % | 54,3 % | 38,2 % |
| K-core | 68,6 % | 51,2 % | 32,8 % |
| Strength | 68,6 % | 51,2 % | 32,8 % |
| Greedy | 69,0 % | 58,1 % | 39,8 % |
| ILP | 69,0 % | 63,5 % | 60,5 % |
| ILP_deg | 69,0 % | 58,1 % | 39,5 % |
| Greedy_edges | 68,3 % | 51,4 % | 32,8 % |
| ILP_edges | 68,3 % | 51,4 % | 32,8 % |

**Valeurs : taux d'attaque moyen. Une valeur faible correspond à moins de personnes infectées.**

Pour k = 10, K-core, Strength, Greedy_edges et ILP_edges obtiennent les meilleurs taux d'attaque moyens (32,8 %), contre 57,7 % pour la sélection aléatoire. Cela représente une réduction relative de 55,2 % par rapport au scénario sans intervention.

L'intervalle de confiance à 95 % de Strength est d'environ [29,9 % ; 35,6 %], contre [55,3 % ; 60,1 %] pour Random.

**Synthèse des meilleures moyennes observées.**

| Budget | SIR uniforme : plus faible taux d’attaque | SIR pondéré : plus faible taux d’attaque |
|---|---|---|
| k = 2 | K-core, Strength : 74,8 % | Greedy_edges, ILP_edges : 68,3 % |
| k = 6 | Degree, PageRank, Closeness : 58,2 % | K-core, Strength : 51,2 % |
| k = 10 | Degree, PageRank, Closeness : 41,9 % | K-core, Strength, Greedy_edges, ILP_edges : 32,8 % |

Ce tableau présente les meilleures moyennes observées dans chaque configuration, sans prétendre à un classement statistique définitif.

**Similarités entre les méthodes.**

Plusieurs méthodes présentent des résultats numériques identiques, notamment Degree, PageRank et Closeness pour k = 10, ainsi que K-core, Strength, Greedy_edges et ILP_edges pour ce même budget. Ces égalités sont compatibles avec des sélections identiques, mais seule une comparaison explicite des fichiers de solutions permettrait de le confirmer.

**Influence du budget d'immunisation.**

Dans les deux modèles, l'augmentation du budget de k = 2 à k = 10 s'accompagne d'une diminution du taux d'attaque moyen pour l'ensemble des méthodes étudiées.

Les différences entre les méthodes sont relativement limitées pour k = 2, mais deviennent plus marquées pour les budgets supérieurs.

Par exemple, dans le modèle pondéré, Strength passe d'un taux d'attaque de 68,6 % avec k = 2 à 51,2 % avec k = 6, puis 32,8 % avec k = 10.

**Couverture du réseau et efficacité épidémiologique.**

Les résultats montrent qu'une couverture maximale des voisinages ne garantit pas une réduction maximale des contaminations.

Dans les deux modèles, l'ILP couverture atteint une couverture de 75 personnes avec k = 10. Pourtant, son taux d'attaque reste de 63,9 % en uniforme et de 60,5 % en pondéré.

À titre de comparaison, Greedy et ILP_deg atteignent également une couverture de 75 personnes, mais obtiennent des taux d'attaque plus faibles.

Ce phénomène s'explique notamment par l'existence de plusieurs sélections optimales pour la couverture, qui n'ont pas nécessairement la même efficacité sur la propagation de l'épidémie.

L'optimalité combinatoire doit donc être distinguée de l'efficacité épidémiologique mesurée par le SIR.

**Compromis entre efficacité et temps de calcul.**

Pour k = 10 dans le modèle pondéré, Greedy_edges et ILP_edges obtiennent le même taux d’attaque moyen (32,8 %) et la même couverture (73 personnes), mais leurs temps de sélection affichés sont respectivement de 0,0070 s et 0,0475 s. Sur cette exécution, le glouton est donc environ 6,8 fois plus rapide. À titre de comparaison, Degree demande environ 0,0001 s et Strength 0,0002 s, pour des taux d'attaque moyens respectifs de 38,2 % et 32,8 %.

Ces temps sont très courts et dépendent de la machine et des conditions d'exécution. Une évaluation fiable des performances nécessiterait des mesures répétées ; une comparaison unique ne permet pas d'affirmer qu'un algorithme est toujours plus rapide.

**Comparaison des modèles uniforme et pondéré.**

Le classement des méthodes varie selon le modèle de transmission.

Pour k = 10, Degree, PageRank et Closeness obtiennent les meilleures moyennes dans le modèle uniforme, tandis que K-core, Strength et les deux méthodes d'optimisation des contacts pondérés obtiennent les meilleures moyennes dans le modèle pondéré.

Ces observations suggèrent que la prise en compte de la durée cumulée des contacts peut modifier l'intérêt des stratégies de sélection.

Cependant, les deux modèles présentent des taux d'attaque différents sans intervention (81,5 % en uniforme et 73,1 % en pondéré). La comparaison directe des taux d'attaque entre modèles doit donc rester prudente. Les réductions relatives sont notamment calculées par rapport à la référence propre à chaque modèle.

**Particularité de la méthode aléatoire.**

La méthode Random utilise 10 tirages de sélections différentes : ses résultats représentent une comparaison de référence qui agrège plusieurs choix possibles de personnes. Les autres méthodes peuvent produire une sélection unique pour chaque budget. Cette différence de protocole doit être prise en compte dans l'interprétation des distributions et des temps de sélection.

**Dispersion et fiabilité des résultats.**

Les expériences reposent sur des simulations stochastiques. Les moyennes sont donc accompagnées d'un écart-type et d'un intervalle de confiance à 95 %, enregistrés dans les fichiers `results.csv`.

Pour k = 10, les intervalles de confiance des méthodes les plus efficaces et de la sélection aléatoire sont nettement séparés. En revanche, les intervalles de plusieurs méthodes performantes se chevauchent, ce qui ne permet pas de les départager sur cette seule base.

Une comparaison statistique directe des différences entre méthodes, idéalement avec des simulations appariées, serait nécessaire pour établir plus précisément leur classement.

Par ailleurs, les résultats concernent un seul réseau hospitalier agrégé, un jeu de paramètres par modèle et des graines aléatoires contrôlées. Leur généralisation à d'autres réseaux ou contextes médicaux n'est pas démontrée.

**Vérification et reproductibilité.**

Les deux expériences hospitalières et l'expérience scolaire ont été soumises au vérificateur indépendant avec l'option `--strict`.

Les 36 solutions du modèle hospitalier uniforme, les 36 solutions du modèle hospitalier pondéré et les 24 solutions du modèle scolaire uniforme ont été déclarées valides, soit **96 solutions valides sur 96**.

Cette vérification confirme le respect des contraintes et des métriques contrôlées par le programme, mais ne prouve pas que toutes les solutions sont optimales.

Les commandes de reproduction des expériences principales sont :

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_uniform_final --k 2 6 10 --runs 200 --random-draws 10 --r0 3 --seed-policy fixed --seed 42 --ilp-time-limit 12
```

```bash
python -m src.run_experiments --input data/raw/hospital.dat.gz --name hospital_weighted_final --transmission weighted --target-attack 0.75 --calibration-runs 100 --k 2 6 10 --runs 200 --random-draws 10 --seed-policy fixed --seed 42 --ilp-time-limit 12
```

Pour reproduire l'expérience finale sur l'école primaire :

```bash
python -m src.run_experiments --input data/raw/primaryschool.csv.gz --name primary_uniform_final --k 5 12 --runs 200 --random-draws 10 --r0 3 --seed-policy fixed --seed 42 --ilp-time-limit 8
```

Ces commandes supposent que les dépendances sont installées et que les données SocioPatterns ont préalablement été téléchargées.

**Bilan.**

Les expériences montrent que l'exploitation de la structure du réseau peut permettre de réduire davantage la propagation simulée qu'une sélection aléatoire. L'efficacité des méthodes dépend toutefois du budget d'immunisation et du modèle de transmission utilisé.

Elles confirment également que la maximisation d'un objectif combinatoire, comme la couverture des voisinages, ne garantit pas la meilleure performance épidémiologique.

Ces résultats constituent une évaluation numérique des stratégies d'immunisation dans un cadre pédagogique et ne doivent pas être interprétés comme des recommandations cliniques.

## 8. Analyse des limites, des échecs et des risques

### 8.1. Limites de l'optimisation

La couverture des voisinages constitue un indicateur structurel du réseau et non une mesure directe du risque épidémique.

Sur un graphe dense, la couverture peut rapidement atteindre 100 %. Plusieurs sélections différentes peuvent alors être optimales pour cet objectif tout en produisant des taux d'attaque différents.

Le choix d'une fonction objectif influence donc les personnes sélectionnées et l'efficacité de l'intervention simulée.

### 8.2. Limites liées aux données

L'agrégation des contacts en un graphe statique entraîne une perte de l'information temporelle : l'ordre chronologique des rencontres n'est plus conservé.

Le poids d'une arête représente une durée cumulée de contact, mais ne constitue pas une probabilité de transmission cliniquement validée.

Les contacts de SocioPatterns ont été observés pendant une période et dans un lieu précis. La généralisation des résultats à d'autres établissements ou populations n'est pas démontrée.

Le choix du seuil de contacts constitue également une hypothèse de prétraitement pouvant modifier la structure du réseau.

### 8.3. Limites biologiques et médicales

Le modèle SIR utilisé repose sur plusieurs simplifications :

- immunisation parfaite des individus sélectionnés ;
- susceptibilité homogène des individus ;
- absence de période d'incubation ;
- absence de réinfection ;
- contacts statiques pendant la simulation ;
- absence de prise en compte des caractéristiques individuelles ;
- probabilités de transmission non validées cliniquement.

Les résultats doivent donc être interprétés comme des résultats de simulation et non comme des prédictions médicales réelles.

### 8.4. Variabilité des simulations

Les infections initiales, les contaminations et les guérisons reposent sur des tirages aléatoires.

Une seule simulation ne suffit donc pas à évaluer l'efficacité d'une stratégie.

Il est nécessaire de répéter les simulations, de contrôler les graines aléatoires et d'interpréter les résultats en tenant compte de leur dispersion.

Des différences de quelques points entre deux méthodes ne permettent pas nécessairement d'affirmer que l'une est meilleure que l'autre.

### 8.5. Limites techniques et reproductibilité

Le temps de résolution de l'ILP peut augmenter avec la taille et la complexité du graphe.

Une limite de temps est définie pour le solveur. En cas d'échec, un repli vers le glouton est prévu et signalé.

Le statut d'optimalité doit être contrôlé avant d'interpréter les résultats.

Les sélections optimales peuvent également varier lorsque plusieurs solutions possèdent la même valeur objectif.

Enfin, les temps de calcul et certains résultats peuvent varier selon la machine, la version de Python et les versions des bibliothèques utilisées.

Les dépendances et les paramètres expérimentaux sont documentés afin de faciliter la reproduction des expériences.

## 9. Extensions possibles

Plusieurs extensions pourraient être envisagées pour améliorer le projet :

- introduire des coûts d'intervention différenciés selon les
  individus et les ressources disponibles ;
- utiliser un graphe temporel afin de conserver l'ordre
  chronologique des contacts ;
- modéliser une véritable stratégie de dépistage avec sensibilité,
  spécificité, délai de résultat et isolement conditionnel ;
- étudier la sensibilité des résultats épidémiques aux paramètres
  beta, gamma, R0 et au seuil de contacts ;
- comparer les méthodes sur d'autres réseaux de contacts ;
- étudier des modèles épidémiologiques plus détaillés ;
- rechercher des fonctions objectifs plus directement liées
  à la réduction de la propagation.

Ces extensions constituent des perspectives d'amélioration et ne sont pas présentées comme des fonctionnalités réalisées dans le MVP actuel.
