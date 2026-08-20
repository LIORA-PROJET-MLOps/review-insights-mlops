# Jeux de données FABSA du POC

Ce répertoire contient les métadonnées reproductibles des trois jeux enregistrés pour le cycle du 20 août 2026. Les avis sources proviennent de `jordiclive/FABSA`, révision immuable `40abb500cd7688529cb831c8c2c2a90d06264379`.

## Jeux enregistrés

| Version | Lignes | Composition |
|---|---:|---|
| `fabsa_real_gold_900_v1` | 900 | 600 entraînement, 150 validation, 150 test aveugle réels |
| `fabsa_real_gold_expanded_v1` | 6 111 | 5 811 entraînement, 150 validation, 150 test aveugle réels |
| `fabsa_real_plus_synthetic_train_v1` | 10 311 | 5 811 lignes réelles et 4 500 ancrages synthétiques d'entraînement |

Chaque manifeste contient les chemins relatifs au dépôt, les empreintes SHA-256, la distribution des classes, les contrôles de qualité, le mapping des thèmes et les partitions verrouillées. Les ensembles de validation et de test du mélange final ne contiennent que des avis réels et zéro ligne de holdout est utilisée pour l'entraînement.

## Reproduction

Depuis la racine du dépôt, après installation des dépendances :

```powershell
python pipelines/build_fabsa_gold_dataset.py
python pipelines/build_fabsa_expanded_dataset.py
python pipelines/generate_scale_datasets.py
python pipelines/build_real_synthetic_training_mix.py
```

Les fichiers CSV et Parquet produits restent ignorés par Git. Les trois fichiers `manifest.json` sont les enregistrements portables versionnés.

## Licence et redistribution

La fiche publique de FABSA ne fournit pas de licence explicite. Pour cette raison, le dépôt ne redistribue pas les textes des avis. Leur téléchargement et leur usage sont réservés au POC local et à la recherche tant que les droits de redistribution ou d'exploitation commerciale n'ont pas été confirmés. La citation bibliographique et l'URL source sont conservées dans les manifestes.
