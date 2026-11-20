# Résultats

- `results/examples/` : **résultats exploratoires mesurés**, issus des jeux réels SocioPatterns disponibles dans les ZIP initiaux ; seuls les résumés CSV/JSON et figures PNG sont conservés.
- `results/<nom>/` : nouvelles expériences générées localement, ignorées par Git.
- `data/processed/<nom>_graph.json` : graphe généré localement, ignoré par Git.

Chaque dossier de résultats contient `results.csv`, `config.json`, des figures et `solutions/*.json`.
Le graphe JSON est reconstruit depuis le jeu d'origine pour utiliser le vérificateur indépendant :

```bash
python -m src.verifier --graph data/processed/hospital_uniform_graph.json --solutions results/hospital_uniform/solutions --strict
```

Les intervalles `attack_ci95_halfwidth` sont approximatifs (1,96 × écart-type / racine du nombre de simulations) ;
ils ne représentent pas des intervalles pour la différence entre méthodes et ne remplacent pas une analyse statistique complète.
Les comparaisons réelles utilisent le même `seed` et les mêmes budgets. Les résultats changent avec le modèle SIR.
Les temps sont dépendants de la machine et ne doivent pas être comparés à des chronométrages réalisés ailleurs.
