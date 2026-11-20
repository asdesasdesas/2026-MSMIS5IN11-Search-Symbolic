# Méthodologie et limites - lecture avant la soutenance

## 1. Objectif d'optimisation (le vrai sujet B5)

Pour un graphe G=(V,E), on choisit exactement k nœuds S.
- **Couverture** : f(S)=|∪_{v∈S}(\{v\}∪N(v))|. Elle maximise le nombre de personnes dans un voisinage fermé.
- **Contacts coupés pondérés** : g(S)=∑_{e=(u,v)∈E} w_e 1[u∈S ou v∈S]. Chaque contact est compté une seule fois.

ILP couverture : x_v∈{0,1}, y_u∈[0,1]. Maximiser ∑y_u sous y_u≤∑_{v∈N[u]}x_v et ∑x_v=k.
ILP contacts : x_v∈{0,1}, z_e∈[0,1]. Maximiser ∑w_e z_e sous z_e≤x_u+x_v et ∑x_v=k.

Les variables auxiliaires peuvent être continues parce que leurs coefficients d'objectif sont non négatifs et le solveur les pousse à 1 dès qu'un élément est couvert.
Les deux fonctions sont **monotones et sous-modulaires** : ajouter un nœud couvre de moins en moins de nouveaux éléments quand la sélection s'agrandit. Le glouton avec budget cardinal k atteint au moins `1-1/e ≈ 0,632` de l'optimum dans ces conditions.
Cette borne porte **sur l'objectif combinatoire**, pas sur le nombre de personnes infectées.

L'ILP renvoie `optimal=True` seulement si HiGHS a prouvé l'optimalité. Si le solveur ne trouve pas de solution, il y a un repli glouton annoncé. L'ILP à départage degré ne valide ce départage qu'après preuve d'optimalité de sa seconde étape.

## 2. Hypothèse médicale : pas de « test » miraculeux

Le SIR suppose une **immunisation / suppression de contacts parfaite et immédiate** pour les personnes ciblées.
Cela correspond à un scénario idéalisé de vaccination ou d'isolement efficace, **pas à un dépistage seul**.
Pour modéliser un vrai test, il faudrait ajouter sensibilité, spécificité, délai de résultat, isolement des positifs, observance et risque de faux négatifs ; ce n'est pas traité dans le MVP.
Il s'agit d'un **modèle pédagogique**, pas d'une recommandation clinique ni d'un outil de tri réel.

## 3. Deux scénarios SIR

- `uniform` (version 1) : chaque arête présente la même probabilité `beta` de transmission à chaque pas.
- `weighted` (idée de la version 2) : `p_ij=1-exp(-beta*w_ij/moyenne(w))`. Une durée cumulée plus élevée augmente le risque supposé. Ce choix est une **hypothèse**, non un étalonnage clinique.
- `seed-policy fixed` : mêmes candidats initiaux dans la population totale pour chaque méthode ; une personne ciblée parmi eux ne devient pas infectieuse (sans remplacement), réduisant la variance de comparaison.
- `seed-policy resample` : version initiale où un cas initial immunisé est remplacé parmi les non-immunisés.

Attention : l'approximation `R0 ≈ 3` de la version non pondérée **ne s'applique pas** directement au scénario pondéré. Pour ce dernier, choisir `--target-attack` (calibration Monte-Carlo) ou fixer `--beta` et documenter le taux d'attaque sans intervention.
La calibration est approximative et peut échouer ; le pipeline le signale.

## 4. Protocole de comparaison équitable

1. Même graphe agrégé, même filtrage, même k et même seed pour les méthodes d'une expérience.
2. Comparer au hasard (plusieurs sélections), au degré et à l'absence d'intervention.
3. Mesurer couverture, contacts coupés, durée de sélection, taux d'attaque moyen et médian, dispersion et probabilité d'épidémie majeure.
4. Indiquer « optimal » seulement si prouvé ; pour un grand graphe, le vérificateur ne calcule pas l'optimum par force brute. Il vérifie les contraintes et métriques, et compare par force brute si le nombre de combinaisons est assez petit.
5. Pour un rendu final solide, augmenter les répétitions (200-1000), répéter plusieurs seeds et étudier la sensibilité à beta/gamma, avant de conclure à une différence de quelques points.
6. Séparer **qualité de l'optimisation** et **performance épidémiologique** : ce ne sont pas les mêmes objectifs.

## 5. Résultats exploratoires livrés

Le dossier `results/examples/` a été généré avec les fichiers bruts hospitaliers et scolaires fournis dans la version 2, **sans inclure ces fichiers dans la remise**. Les paramètres exacts se trouvent dans chaque `config.json`. Les tailles d'échantillon (35 ou 55 répétitions) sont **trop faibles pour une affirmation clinique** et servent à préparer l'oral et la reproduction.

## 6. Analyse des échecs et risques

- Couverture des voisinages = proxy structurel qui peut saturer sur les graphes denses : plusieurs sélections ILP différentes obtiennent 100 % de couverture mais pas le même taux SIR.
- Durées agrégées = proxy de risque imparfait : séquences temporelles effacées, poids d'arête ≠ probabilité de transmission validée.
- Les contacts sont observés sur une période et un lieu précis ; généralisation à d'autres contextes non prouvée.
- Immunisation parfaite, homogénéité de susceptibilité, absence d'incubation et contacts statiques sont des limites biologiques.
- Cas initiaux aléatoires ; varier les scénarios d'importation et les seeds.
- Temps solveur soumis à limite, avec repli signalé ; statut d'optimalité contrôlé.
- Les figures peuvent être différentes suivant versions Python, NumPy, SciPy et machine.
- Les solutions optimales ILP dépendent du solveur et des égalités ; les méthodes déterministes sont triées autant que possible.

## 7. Extensions possibles (non incluses)

Coûts différenciés (knapsack), vrai graphe temporel avec horaires de contacts, tests avec sensibilité/spécificité et stratégie conditionnelle, validation épidémiologique sur d'autres réseaux. Ne pas annoncer ces extensions comme réalisées.
