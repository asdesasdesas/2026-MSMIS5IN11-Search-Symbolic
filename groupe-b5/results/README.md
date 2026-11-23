
# Résultats expérimentaux du projet B5

## 1. Présentation

Ce dossier regroupe les résultats de nos expériences d'optimisation et de simulation épidémiologique SIR.

Nous avons comparé différentes méthodes de sélection de personnes à immuniser, notamment les méthodes aléatoires, les centralités, les algorithmes gloutons et les formulations ILP.

Les principales mesures étudiées sont :
- La couverture du réseau.
- Le poids total des contacts coupés.
- Le temps de calcul.
- Le taux d'attaque moyen.
- La probabilité d'épidémie majeure.
- La réduction de la propagation par rapport à l'absence d'intervention.

## 2. Organisation des résultats


## 2. Organisation des résultats

Le dossier `examples/` contient les trois expériences finales réalisées sur les données SocioPatterns.

| Dossier | Description |
|---|---|
| `hospital_uniform_final/` | Expérience finale sur l'hôpital avec le SIR uniforme |
| `hospital_weighted_final/` | Expérience finale sur l'hôpital avec le SIR pondéré |
| `primary_uniform_final/` | Expérience finale sur l'école primaire avec le SIR uniforme |

Les trois expériences utilisent 200 simulations SIR par sélection évaluée. Les résultats numériques, les paramètres et les graphiques sont conservés pour permettre leur consultation et leur comparaison.


## 3. Contenu des dossiers d'expériences

Chaque dossier d'exemples contient notamment :

- `results.csv` : résultats numériques des différentes méthodes et des budgets d'immunisation.
- `config.json` : paramètres utilisés pour réaliser l'expérience.
- `attack_rate_vs_k.png` : évolution du taux d'attaque selon le budget.
- `p_major_vs_k.png` : probabilité d'épidémie majeure selon le budget.
- `objective_vs_attack.png` : relation entre les objectifs d'optimisation et le taux d'attaque.
- `time_vs_k.png` : temps de calcul des méthodes selon le budget.
- `quality_vs_time.png` : compromis entre la qualité des solutions et le temps de calcul.

## 4. Expériences hospitalières finales

Les deux expériences finales utilisent :

- 75 personnes et 1 139 arêtes.
- Trois budgets d'immunisation : k = 2, 6 et 10.
- 200 simulations SIR par sélection évaluée.
- 10 tirages de sélections pour la méthode aléatoire.
- Une graine aléatoire fixée à 42.
- Une probabilité de guérison gamma = 0,2.

### Modèle SIR uniforme

Le paramètre beta est déterminé à partir d'un R0 cible de 3.

Le taux d'attaque moyen sans intervention est de **81,5 %**.

Pour k = 10, les méthodes Degree, PageRank et Closeness obtiennent les taux d'attaque moyens les plus faibles : **41,9 %**.

### Modèle SIR pondéré

La transmission dépend du poids des contacts. Le paramètre beta est calibré pour approcher un taux d'attaque cible de 75 % sans intervention.

Le taux d'attaque moyen de référence obtenu dans l'évaluation finale est de **73,1 %**.

Pour k = 10, K-core, Strength, Greedy_edges et ILP_edges obtiennent les taux d'attaque moyens les plus faibles : **32,8 %**.

## 5. Expérience sur le réseau de l'école primaire

Nous avons également réalisé une expérience sur le réseau de l'école primaire, composé de **242 personnes et de 8 317 arêtes**.

Cette expérience utilise le modèle SIR uniforme avec :

- Deux budgets d'immunisation : k = 5 et k = 12.
- 200 simulations SIR par sélection évaluée.
- 10 tirages de sélections pour la méthode aléatoire.
- Une graine aléatoire fixée à 42.
- Un R0 cible de 3.
- Une probabilité de guérison gamma = 0,2.

Le taux d'attaque moyen sans intervention est de **83,2 %**.

Pour k = 12, plusieurs méthodes atteignent une couverture totale du réseau, mais leurs performances épidémiologiques diffèrent :

| Méthode | Couverture | Réduction du taux d'attaque |
|---|---:|---:|
| Greedy | 242 / 242 | 12,4 % |
| ILP | 242 / 242 | 10,2 % |
| ILP_deg | 242 / 242 | 14,0 % |

La méthode ILP_deg obtient la réduction moyenne la plus importante parmi les méthodes évaluées pour k = 12.

Ces résultats confirment qu'une couverture maximale du réseau ne garantit pas nécessairement la réduction la plus importante des infections.

## 6. Interprétation des résultats

Nos expériences montrent que l'augmentation du budget d'immunisation réduit généralement la propagation simulée.

Les méthodes les plus efficaces dépendent cependant du modèle de transmission utilisé.

Nous observons également qu'une méthode optimale pour la couverture du réseau n'est pas nécessairement celle qui réduit le plus les infections.

Ces résultats concernent des simulations pédagogiques reposant sur plusieurs hypothèses simplificatrices, notamment une immunisation parfaite et immédiate.

## 7. Vérification et reproductibilité

Les solutions des deux expériences hospitalières finales et de l'expérience sur l'école primaire ont été contrôlées avec notre vérificateur indépendant.

Au total, **96 solutions sur 96 ont été déclarées valides** :

- 36 solutions pour l'hôpital avec le SIR uniforme.
- 36 solutions pour l'hôpital avec le SIR pondéré.
- 24 solutions pour l'école primaire avec le SIR uniforme.

Les scripts de reproduction et les commandes d'exécution sont décrits dans le README principal du projet.

Les analyses détaillées, les intervalles de confiance et les limites des expériences sont présentés dans :

`docs/ANALYSE_METHODOLOGIQUE.md`
