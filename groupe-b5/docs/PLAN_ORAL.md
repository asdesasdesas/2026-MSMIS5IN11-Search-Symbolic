# Guide pour défendre le projet à l'oral

**Ouverture** : « Avec k doses ou isolements, qui cibler ? Notre innovation est l'optimisation de la sélection sur un réseau de contacts, pas un modèle d'apprentissage supervisé. »

**Méthodes** : expliquer variables binaires de l'ILP, contraintes de budget exact, couverture des voisinages, glouton marginal, borne 1−1/e, baseline degré et aléatoire.

**Expérience** : SocioPatterns hôpital et école ; même graphe et k pour chaque méthode, SIR simulé seulement pour évaluer, 2 hypothèses de transmission, fichiers CSV avec durées et incertitudes.

**Observation à défendre** : couverture optimale ≠ meilleure réduction des infections ; saturation sur graphe dense et rôle des poids de contact.

**Question difficile** : « Vous parlez de tests mais immunisez directement ! » → Oui, nous avons modélisé une intervention parfaite de prévention/isolement, ce qui est une limite de validité clinique ; un vrai dépistage requiert sensibilité/spécificité et politique d'isolement des positifs.

**Autres questions** : (1) optimum ILP prouvé vs limite de temps ; (2) pourquoi le glouton a une garantie ; (3) pourquoi plusieurs baselines ; (4) sources des données ; (5) rôle des graines de simulation ; (6) coût de calcul sur graphes plus grands ; (7) différence entre qualité de couverture et qualité SIR.

**Démonstration de secours** : utiliser `--synthetic` ; sorties existantes dans `results/examples/` + slides si réseau indisponible.
