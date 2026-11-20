# Checklist finale - à cocher par les deux membres

- [ ] **Remplacer `@pseudo1` et `@pseudo2`** par vos vrais comptes GitHub ; confirmer la répartition de travail proposée, sans inventer de contributions.
- [ ] Confirmer ensemble la licence du code (une proposition MIT figure dans `docs/LICENCE_CODE_A_VALIDER.md`).
- [ ] Tester une installation propre : `pip install -r requirements-lock.txt` (ou `requirements.txt` selon OS).
- [ ] Exécuter `python -m pytest -q` et recopier la sortie et la version Python dans le compte rendu.
- [ ] Tester la démo sans Internet : `python -m src.run_experiments --synthetic --name demo --k 2 4 --runs 30`.
- [ ] Sur vraies données, exécuter les commandes de reproduction du README ; garder `config.json`.
- [ ] Vérifier les solutions : `python -m src.verifier --graph data/processed/hospital_uniform_graph.json --solutions results/hospital_uniform/solutions --strict`.
- [ ] Vérifier que `.venv/`, `data/raw/`, `data/processed/`, `.env` et archives lourdes ne sont **pas** suivis.
- [ ] Vérifier les slides : cohérence des chiffres, nom du groupe, durée de la présentation et réponses aux questions.
- [ ] Vérifier les deux contributions dans l'historique Git : `git log --all --format='%an: %s' -- groupe-b5` ; si les contributions Git réelles diffèrent du tableau proposé, le corriger.
- [ ] Insérer **un seul** dossier `groupe-b5/` à la racine du fork du cours, pas le contenu du ZIP tel quel à la racine sans vérification.
- [ ] `git diff --stat upstream/main...HEAD` doit ne montrer que `groupe-b5/` (ou le nom de votre dossier).
- [ ] Ouvrir une PR vers `jsboigeEPF/2026-MSMIS5IN11-Search-Symbolic:main` **avant lundi 23 novembre 2026 à 23h59**.
- [ ] Remplir la checklist de PR et vérifier la PR sur GitHub.
- [ ] Préparer la soutenance du mercredi 25 novembre 2026 (salle A202 C) ; chaque membre explique théories, mesures et limites.

**À ne pas faire :** déduire des contributions Git de la présence d'un code dans le ZIP ; le ZIP n'a pas d'historique Git. Ne pas prétendre que les 55 répétitions exploratoires constituent une preuve de supériorité statistique.
