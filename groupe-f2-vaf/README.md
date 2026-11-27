# F2 — Prototype Dung / VAF

Prototype pédagogique en Python standard, inspiré des notebooks de cours :
- `Argumentation-03-Dung-AF-Semantics-Python` ;
- `Argumentation-03b-Value-Based-AF-Python`.

## Lancer le projet (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python src/main.py
python -m unittest discover -s tests -v
```

Aucune dépendance externe n'est nécessaire.

## Organisation

- `src/argumentation.py` : primitives Dung et transformation VAF -> AF selon l'audience.
- `src/medical_case.py` : arguments, valeurs, attaques et profils d'audience fictifs.
- `src/main.py` : exécution et comparaison Dung / VAF.
- `tests/` : tests ciblés des règles centrales.

## Correspondance avec les notebooks

- Dung : `AF`, `attackers`, `is_conflict_free`, `defeats`, `defends`,
  `is_admissible`, `powerset`, `grounded`, `preferred`, `stable`.
- Compléments également présents dans le notebook Dung : `range_of`,
  `semi_stable`, `ideal`.
- VAF : `VAF`, `audience_rank`, `defeats_under_audience`, `af_from_audience`.

Les noms et la logique des fonctions sont conservés autant que possible. Les
vérifications d'entrée et la séparation du scénario médical sont des ajouts
pratiques au projet.

## Limites

Le scénario médical est fictif. Les attaques et les préférences sont des hypothèses
de démonstration à justifier/valider avec le binôme. Ce prototype ne constitue pas
un outil d'aide clinique validé. Le calcul par énumération des sous-ensembles est
adapté aux petits graphes pédagogiques, pas aux grandes instances.
