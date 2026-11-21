# Méthodologie et limites du projet B5

## 1. Objectifs d'optimisation

L'objectif du projet est de déterminer quelles personnes cibler en priorité
sur un réseau de contacts, avec un budget d'intervention limité, afin de
réduire la propagation d'une épidémie.

Pour un graphe G = (V, E), on cherche à sélectionner exactement k nœuds
formant un ensemble S.

Deux objectifs d'optimisation sont étudiés :

- **Couverture des voisinages** :
  f(S) = |∪_{v∈S} ({v} ∪ N(v))|.
  L'objectif est de maximiser le nombre de personnes couvertes.
  Une personne est considérée comme couverte si elle est sélectionnée
  ou si elle est voisine d'au moins une personne sélectionnée.

- **Contacts coupés pondérés** :
  g(S) = ∑_{e=(u,v)∈E} w_e × 1[u∈S ou v∈S].
  L'objectif est de maximiser le poids total des contacts neutralisés
  par la sélection. Chaque arête est comptée une seule fois, même si
  ses deux extrémités sont sélectionnées.

### Formulation ILP

Pour la couverture des voisinages :

- x_v ∈ {0,1} : indique si le nœud v est sélectionné ;
- y_u ∈ [0,1] : indique si le nœud u est couvert ;
- objectif : maximiser ∑ y_u ;
- contraintes : y_u ≤ ∑_{v∈N[u]} x_v et ∑ x_v = k.

Pour les contacts coupés pondérés :

- x_v ∈ {0,1} : indique si le nœud v est sélectionné ;
- z_e ∈ [0,1] : indique si l'arête e est neutralisée ;
- objectif : maximiser ∑ w_e z_e ;
- contraintes : z_e ≤ x_u + x_v et ∑ x_v = k.

Les variables auxiliaires peuvent être continues, car leurs coefficients
dans la fonction objectif sont non négatifs et la maximisation permet
d'atteindre la valeur 1 lorsqu'un élément est couvert.

### Propriétés de l'algorithme glouton

Les deux fonctions objectifs sont **monotones et sous-modulaires**.

Cela signifie que l'ajout d'un nœud à une sélection ne diminue pas la
valeur de l'objectif, mais que son apport supplémentaire tend à diminuer
lorsque la sélection s'agrandit.

Pour ces fonctions et sous une contrainte de cardinalité k, l'algorithme
glouton garantit au moins 1 - 1/e ≈ 63,2 % de la valeur optimale.

Cette garantie concerne uniquement **l'objectif d'optimisation
combinatoire**, et non directement la réduction du nombre de personnes
infectées dans la simulation SIR.

### Gestion de l'optimalité

L'ILP renvoie `optimal=True` uniquement lorsque le solveur HiGHS a
prouvé l'optimalité de la solution.

Si le solveur ne trouve aucune solution exploitable, un repli vers
l'algorithme glouton est prévu et signalé.

Pour l'ILP avec départage par degré, l'optimalité du départage n'est
validée qu'après preuve d'optimalité de la seconde étape.


## 2. Hypothèses médicales

Dans notre modèle, les personnes sélectionnées bénéficient d'une
**immunisation parfaite et immédiate**.

Elles ne peuvent donc plus être infectées ni transmettre la maladie.
Cela revient également à neutraliser leurs contacts du point de vue
de la transmission.

Cette hypothèse correspond à un scénario idéalisé de vaccination
parfaitement efficace ou d'isolement complet, et non à un simple
dépistage.

En effet, un test de dépistage ne permet pas directement d'empêcher
une contamination. Pour représenter une véritable stratégie de
dépistage, il faudrait notamment prendre en compte :

- la sensibilité et la spécificité des tests ;
- le délai d'obtention des résultats ;
- l'isolement des personnes positives ;
- l'observance des mesures d'isolement ;
- le risque de faux négatifs.

Ces éléments ne sont pas modélisés dans le MVP.

Notre projet constitue donc un **modèle pédagogique d'aide à la
sélection**, et non une recommandation clinique ou un outil de tri
utilisable directement dans un établissement de santé.


## 3. Modèles de simulation SIR

Le modèle SIR permet d'évaluer les sélections obtenues par les
différents algorithmes d'optimisation.

Chaque personne peut se trouver dans l'un des états suivants :

- S (Susceptible) : personne susceptible d'être infectée ;
- I (Infectious) : personne infectée et contagieuse ;
- R (Recovered) : personne guérie ou retirée de la transmission ;
- IMMUNE : personne immunisée par l'intervention.

À chaque pas de simulation, les personnes infectées peuvent transmettre
la maladie à leurs voisins susceptibles, puis guérir selon une
probabilité gamma.

Les nouvelles contaminations deviennent contagieuses au pas suivant.

### 3.1. SIR uniforme

Dans le modèle `uniform`, toutes les arêtes possèdent la même
probabilité de transmission beta à chaque pas de simulation.

La durée cumulée des contacts n'intervient donc pas directement
dans la probabilité de transmission.

Le paramètre beta est calibré à partir des caractéristiques du
graphe, de la probabilité de guérison gamma et d'un nombre de
reproduction de base R0 cible.

Dans nos expériences principales, le scénario uniforme utilise
un R0 cible de 3 et une probabilité de guérison gamma de 0,2.

Une valeur de gamma égale à 0,2 correspond à une probabilité de
guérison de 20 % à chaque pas, soit une durée infectieuse moyenne
de cinq pas de simulation.

Ces pas ne correspondent pas nécessairement à une durée médicale
réelle, comme une journée.

### 3.2. SIR pondéré

Dans le modèle `weighted`, la probabilité de transmission dépend
du poids de chaque arête :

p_ij = 1 - exp(-beta × w_ij / moyenne(w))

avec :

- beta : paramètre global de transmission ;
- w_ij : poids du contact entre les personnes i et j ;
- moyenne(w) : poids moyen des arêtes du graphe ;
- p_ij : probabilité de transmission associée à cette arête.

Une durée cumulée de contact plus importante entraîne donc une
probabilité de transmission plus élevée dans le modèle.

Cette relation constitue une **hypothèse de modélisation** et non
un étalonnage clinique validé.

### 3.3. Calibration des paramètres

L'approximation de R0 utilisée dans le modèle uniforme ne s'applique
pas directement au modèle pondéré.

Pour le scénario pondéré, il est possible d'utiliser :

- `--target-attack` : calibration de beta par simulations
  Monte-Carlo afin d'atteindre un taux d'attaque cible sans intervention ;
- `--beta` : utilisation d'une valeur de beta fixée directement,
  en documentant le taux d'attaque obtenu sans intervention.

La calibration est approximative et peut ne pas atteindre la cible.
Le programme signale cette situation.

Les deux modèles ne sont donc pas nécessairement calibrés au même
niveau de propagation initiale. Leurs résultats doivent être
comparés en tenant compte de cette différence.

### 3.4. Sélection des cas initiaux

Deux stratégies de sélection des cas initiaux sont disponibles :

- `seed-policy fixed` : les mêmes candidats à l'infection initiale
  sont utilisés pour comparer les méthodes. Si une personne ciblée
  par l'intervention fait partie de ces candidats, elle ne devient
  pas infectieuse et n'est pas remplacée.

- `seed-policy resample` : lorsqu'un candidat initial est immunisé,
  il est remplacé par une personne non immunisée.

La stratégie `fixed` permet de comparer les interventions à partir
des mêmes candidats initiaux et de prendre en compte la prévention
des infections initiales.

La répétition des simulations permet de limiter l'influence des
tirages aléatoires sur les résultats.


## 4. Protocole de comparaison équitable

Afin de comparer les différentes méthodes de sélection dans des
conditions similaires, le protocole suivant est utilisé :

1. Utiliser le même graphe agrégé, le même seuil de filtrage et
   le même budget k pour toutes les méthodes d'une expérience.

2. Conserver les mêmes paramètres épidémiques beta et gamma
   pour comparer les interventions au sein d'une même expérience.

3. Utiliser des graines aléatoires contrôlées afin de permettre
   la reproduction des simulations.

4. Comparer les algorithmes d'optimisation à des méthodes de
   référence simples : sélection aléatoire, centralité degré
   et absence d'intervention.

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
   Celui-ci contrôle notamment les contraintes de sélection et
   recalcule les métriques annoncées. Pour les petits graphes,
   une comparaison par force brute peut également être réalisée.

7. Indiquer qu'une solution est optimale uniquement lorsque
   son optimalité a été prouvée.

8. Augmenter le nombre de répétitions des simulations
   (200 à 1000) et, si possible, étudier la sensibilité aux
   paramètres beta, gamma et aux graines aléatoires.

Il est essentiel de distinguer **la qualité de l'optimisation
combinatoire** de **la performance épidémiologique**.

Une solution optimale pour la couverture des voisinages ne garantit
pas nécessairement le taux d'attaque le plus faible.


## 5. Influence du seuil de contacts sur la construction du graphe

### 5.1. Principe

Les données SocioPatterns enregistrent les contacts entre deux
personnes par intervalles de 20 secondes.

Lors de la construction du graphe statique :

- un nœud représente une personne ;
- une arête représente une relation de contact ;
- le poids d'une arête correspond au nombre d'intervalles de
  contact enregistrés entre les deux personnes.

Le paramètre `min_contacts` correspond au poids minimal nécessaire
pour conserver une arête dans le graphe.

Par exemple, un seuil de 2 permet de conserver uniquement les
relations de contact dont la durée cumulée est supérieure ou
égale à 40 secondes.

Afin d'étudier l'influence du prétraitement des données sur la
structure du réseau hospitalier, nous avons testé plusieurs valeurs
de ce paramètre.

### 5.2. Résultats obtenus

| Seuil | Durée cumulée minimale | Nœuds | Arêtes | Nœuds isolés | Densité |
|---|---|---|---|---|---|
| 1 | 20 s | 75 | 1139 | 0 | 0,4105 |
| 2 | 40 s | 75 | 976 | 0 | 0,3517 |
| 5 | 100 s | 75 | 722 | 2 | 0,2602 |
| 10 | 200 s | 75 | 505 | 3 | 0,1820 |

La densité représente la proportion d'arêtes présentes dans le
graphe par rapport au nombre maximal d'arêtes possibles.

Pour un graphe non orienté sans boucle, elle est calculée par :

Densité = 2E / (N × (N - 1))

avec N le nombre de nœuds et E le nombre d'arêtes.

### 5.3. Analyse des résultats

On observe que lorsque le seuil augmente, le nombre d'arêtes
et la densité du graphe diminuent, tandis que le nombre de
nœuds reste constant.

Entre les seuils 1 et 10, le nombre d'arêtes passe de 1139
à 505, soit une diminution d'environ 55,7 %.

La densité du réseau passe également de 41,05 % à 18,20 %.

Pour les seuils de 5 et 10, certains individus deviennent
isolés, car aucun de leurs contacts ne possède un poids
suffisant pour être conservé dans le graphe.

Le choix du seuil peut donc influencer :

- la structure et la densité du réseau ;
- le nombre de voisins de chaque individu ;
- les mesures de centralité ;
- les personnes sélectionnées par les algorithmes ;
- la calibration du paramètre beta ;
- les résultats des simulations épidémiques.

Cependant, une diminution du nombre d'arêtes ne garantit pas
nécessairement une réduction du taux d'attaque, notamment si
beta est recalibré pour conserver le même R0 cible.

Cette expérience étudie uniquement l'influence du seuil sur
la structure du graphe. Elle ne mesure pas directement son
influence sur les résultats SIR.

### 5.4. Justification du seuil retenu

Pour nos expériences principales, nous conservons un seuil
`min_contacts = 1` afin de ne pas négliger les contacts de
courte durée.

Le modèle SIR pondéré permet ensuite de différencier les
probabilités de transmission selon la durée cumulée des contacts.

Ce choix permet de conserver l'ensemble des relations de contact
enregistrées, tout en étudiant l'influence de leur durée dans
le scénario pondéré.

### 5.5. Reproduction de l'expérience

Depuis le dossier `groupe-b5`, après installation des dépendances
et activation de l'environnement Python, télécharger les données
hospitalières :

```bash
python data/download_data.py hospital_raw
```

Puis exécuter la commande suivante :

```bash
python -c "from src.data import load_graph; import networkx as nx; [print('Seuil :', s, '| Noeuds :', G.number_of_nodes(), '| Aretes :', G.number_of_edges(), '| Isoles :', nx.number_of_isolates(G), '| Densite :', round(nx.density(G),4)) for s in [1,2,5,10] for G in [load_graph('data/raw/hospital.dat.gz',min_contacts=s)]]"
```

Les données téléchargées restent dans le dossier `data/raw/`
et ne sont pas versionnées sur GitHub.


## 6. Résultats exploratoires

Le dossier `results/examples/` contient les premiers résultats
obtenus à partir des données hospitalières et scolaires, sans
inclure les fichiers de données brutes dans le dépôt.

Les paramètres exacts de chaque expérience sont enregistrés
dans les fichiers `config.json`.

Les fichiers `results.csv` contiennent les mesures obtenues
pour chaque méthode et chaque budget d'intervention.

Les graphiques permettent notamment de comparer :

- l'évolution du taux d'attaque selon le budget k ;
- la probabilité d'épidémie majeure ;
- la relation entre les objectifs d'optimisation et le taux
  d'attaque ;
- le temps de calcul des méthodes ;
- le compromis entre la qualité des solutions et le temps
  de calcul.

Les premières expériences, réalisées avec 35 ou 55 répétitions
demandées selon le jeu de données, constituent des résultats
exploratoires.

Le nombre effectif de simulations peut dépendre de la méthode,
notamment pour la sélection aléatoire qui utilise plusieurs
ensembles de personnes sélectionnées.

Ces résultats permettent d'illustrer le fonctionnement du projet,
mais ne sont pas suffisants pour établir des conclusions cliniques.

L'augmentation du nombre de simulations et l'étude de la
variabilité des résultats permettent d'améliorer la robustesse
des comparaisons.


## 7. Analyse des limites, des échecs et des risques

### 7.1. Limites de l'optimisation

La couverture des voisinages constitue un indicateur structurel
du réseau et non une mesure directe du risque épidémique.

Sur un graphe dense, la couverture peut rapidement atteindre
100 %. Plusieurs sélections différentes peuvent alors être
optimales pour cet objectif tout en produisant des taux
d'attaque différents.

Le choix d'une fonction objectif influence donc les personnes
sélectionnées et l'efficacité de l'intervention simulée.

### 7.2. Limites liées aux données

L'agrégation des contacts en un graphe statique entraîne une
perte de l'information temporelle : l'ordre chronologique
des rencontres n'est plus conservé.

Le poids d'une arête représente une durée cumulée de contact,
mais ne constitue pas une probabilité de transmission
cliniquement validée.

Les contacts de SocioPatterns ont été observés pendant une
période et dans un lieu précis. La généralisation des résultats
à d'autres établissements ou populations n'est pas démontrée.

Le choix du seuil de contacts constitue également une hypothèse
de prétraitement pouvant modifier la structure du réseau.

### 7.3. Limites biologiques et médicales

Le modèle SIR utilisé repose sur plusieurs simplifications :

- immunisation parfaite des individus sélectionnés ;
- susceptibilité homogène des individus ;
- absence de période d'incubation ;
- absence de réinfection ;
- contacts statiques pendant la simulation ;
- absence de prise en compte des caractéristiques individuelles ;
- probabilités de transmission non validées cliniquement.

Les résultats doivent donc être interprétés comme des résultats
de simulation et non comme des prédictions médicales réelles.

### 7.4. Variabilité des simulations

Les infections initiales, les contaminations et les guérisons
reposent sur des tirages aléatoires.

Une seule simulation ne suffit donc pas à évaluer l'efficacité
d'une stratégie.

Il est nécessaire de répéter les simulations, de contrôler les
graines aléatoires et d'interpréter les résultats en tenant
compte de leur dispersion.

Des différences de quelques points entre deux méthodes ne
permettent pas nécessairement d'affirmer que l'une est
meilleure que l'autre.

### 7.5. Limites techniques et reproductibilité

Le temps de résolution de l'ILP peut augmenter avec la taille
et la complexité du graphe.

Une limite de temps est définie pour le solveur. En cas d'échec,
un repli vers le glouton est prévu et signalé.

Le statut d'optimalité doit être contrôlé avant d'interpréter
les résultats.

Les sélections optimales peuvent également varier lorsque
plusieurs solutions possèdent la même valeur objectif.

Enfin, les temps de calcul et certains résultats peuvent
varier selon la machine, la version de Python et les versions
des bibliothèques utilisées.

Les dépendances et les paramètres expérimentaux sont documentés
afin de faciliter la reproduction des expériences.


## 8. Extensions possibles

Plusieurs extensions pourraient être envisagées pour améliorer
le projet :

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

Ces extensions constituent des perspectives d'amélioration
et ne sont pas présentées comme des fonctionnalités réalisées
dans le MVP actuel.