# Traçabilité de la fusion des deux ZIP

Ce document décrit **ce qui a été conservé, ajouté, réécrit et testé** lors de la préparation de la version fusionnée. Il ne prouve pas les contributions personnelles de chacun des deux membres ; celles-ci doivent être validées dans le README et l'historique du dépôt.

## Base : ZIP 1 (`groupe-b5(1).zip`)

Conservés : `src/data.py`, algorithmes ILP / glouton / centralités historiques de `src/selection.py`, vérificateur standard library, pipeline d'expériences, figures, tests spécialisés et structure du projet.

Corrections : l'étape de départage `ilp_deg` ne revendique plus le résultat de la deuxième optimisation que si son optimalité a été prouvée. Le vérificateur accepte un mode `--strict` et traite plus proprement les valeurs invalides de `k` et les identifiants de mauvaise forme. Le pipeline vérifie ses solutions et échoue explicitement si un résultat est invalide.

## Idées adaptées de ZIP 2 (`groupe-b5-contacts_V3.zip`)

1. Simulation SIR `weighted` : `p_ij = 1 - exp(-beta × w_ij / mean(w))`, avec contrôles de poids strictement positifs et exposé des hypothèses.
2. Nouvelle méthode de calibration de beta sur un taux d'attaque sans intervention fixé, avec détection de cible inaccessible.
3. Deux nouvelles centralités : `closeness` et `kcore`.
4. Utilisation d'un deuxième jeu réel, l'école primaire SocioPatterns, et de figures expérimentales directement réutilisables.

## Intégrations complémentaires

- `--seed-policy fixed` : mêmes candidats initiaux avant intervention, sans remplacement des individus immunisés ; `resample` conserve le comportement V1.
- Version de dépendances effectivement testées, fichier `.env.example`, `.gitignore` excluant données et `.venv`.
- README réécrit, étude théorique/médicale, checklist de PR, guide oral et notebook d'analyse actualisé.
- Supports de soutenance modifiables (PPTX) et de présentation (PDF).
- Nouveaux tests de non-régression `tests/test_fusion.py` : **147 tests réussis au total** lors de la fabrication.
- Résultats exploratoires réels : hôpital uniforme/pondéré et école uniforme ; uniquement des CSV/PNG/JSON agrégés. **Fichiers de contacts exclus.**

## Arbitrages et limites de la fusion

- La version 1 reste la base de l'optimisation (égalité de budget `sum x = k`, solveur SciPy/HiGHS). Le backend PuLP/CBC de la version 2 n'a **pas** été fusionné : dépendance supplémentaire sans nécessité pour le MVP.
- Un mode SIR pondéré ne prouve pas que la durée des contacts permet de prédire des infections réelles ; il permet d'étudier la sensibilité à une hypothèse.
- Le coût différencié et le graphe temporel restent des **extensions non réalisées**, clairement identifiées.
- Une licence de code définitive requiert la validation des deux membres. Aucun historique Git ne peut être reconstitué honnêtement à partir des archives ZIP.
