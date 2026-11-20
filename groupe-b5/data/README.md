# Provenance, récupération et licence des données

**Les jeux de données téléchargés ne doivent pas être inclus dans le dépôt Git ou l'archive de remise.**
Le dossier `data/raw/` est exclu par `.gitignore`; `data/processed/` contient uniquement des graphes JSON générés.
Les CSV présents dans `results/examples/` sont des **statistiques agrégées**, pas des fichiers de contacts.

| Jeu | Origine publique | Format |
| --- | --- | --- |
| Hôpital | [SocioPatterns - Hospital ward dynamic contact network](http://www.sociopatterns.org/datasets/hospital-ward-dynamic-contact-network/) | `hospital.dat.gz` (`t i j statut_i statut_j`) |
| École primaire | [SocioPatterns - Primary school](http://www.sociopatterns.org/datasets/primary-school-temporal-network-data/) | `primaryschool.csv.gz` (`t i j classe_i classe_j`) |
| Lycée | [SocioPatterns - High school](http://www.sociopatterns.org/datasets/high-school-dynamic-contact-networks/) | miroir Netzschleuder ZIP |
| Synthétique | `src/data.py::synthetic_graph` | génération Python, aucune donnée externe |

Les identifiants sont des pseudonymes publics, mais il faut conserver les restrictions de redistribution.
Licence des jeux SocioPatterns indiquée dans la documentation d'origine : **CC BY-NC-SA 3.0** ;
vérifier la licence affichée pour la version exacte téléchargée avant toute redistribution.

## Télécharger sans commiter

```bash
python data/download_data.py hospital_raw
python data/download_data.py primary_school_raw
# Alternative hospitalier si l'URL brute échoue :
python data/download_data.py hospital
```

Si l'hébergeur change une URL, le script affiche le lien et la page source de provenance :
téléchargez manuellement le `.gz` d'origine et placez-le sous le nom attendu dans `data/raw/`.
Les téléchargements ne sont **jamais nécessaires** pour la démo synthétique.

## Construction des graphes

Une ligne représente une observation d'un contact face-à-face de 20 s. L'agrégation produit un graphe statique non orienté :
une personne = un nœud, chaque paire = une arête de poids égal au nombre de tranches de 20 s observées.
Les paramètres `--min-contacts` filtrent les arêtes, sans supprimer les personnes devenues isolées.
Attention : l'agrégation fait disparaître l'ordre temporel des contacts (limite importante).

## Références de jeux

- Vanhems et al. (2013), *Estimating Potential Infection Transmission Routes in Hospital Wards Using Wearable Proximity Sensors*, PLoS ONE 8(9), e73970.
- Stehlé et al. (2011), *High-Resolution Measurements of Face-to-Face Contact Patterns in a Primary School*, PLoS ONE 6(8), e23176.
- Fournet et al. (2014), *Contact Patterns among High School Students*, PLoS ONE 9(9), e107878.
