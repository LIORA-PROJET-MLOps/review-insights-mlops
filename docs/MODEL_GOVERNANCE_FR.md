# Gouvernance modele et MLflow - Review Insights+

## Architecture

La couche MLflow locale partagee utilise:

- PostgreSQL pour les runs, metadonnees et versions de modeles
- MinIO pour les artefacts de runs et de modeles
- MLflow Model Registry avec des alias, pas les anciens stages fixes

Alias utilises:

- `candidate`: derniere version enregistree par la pipeline de training
- `champion`: version approuvee pour deploiement
- `previous_champion`: version precedente disponible pour rollback

La politique versionnee est `config/model_promotion_policy_v1.json` (`policy_version` 1.1.0).

## Demarrage

Creer un fichier `.env` local a partir de `.env.example` et remplacer les mots de passe avant tout
environnement partage.

```powershell
docker compose up -d --build postgres minio minio-init mlflow
```

Interfaces:

- MLflow: `http://localhost:5000`
- MinIO API: `http://localhost:9100`
- MinIO console: `http://localhost:9101`

Les valeurs par defaut de Compose sont reservees au developpement local.

## Enregistrer une candidate

```powershell
$env:MLFLOW_TRACKING_ENABLED="true"
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
$env:MLFLOW_EXPERIMENT_NAME="review-insights-training"

py -3 pipelines/train_models.py `
  --dataset-path data/validated/training_dataset_<version>.parquet `
  --evaluation-dataset-path data/splits/<version>/test.parquet `
  --mlflow-log `
  --register-model `
  --model-alias candidate
```

La candidate doit etre evaluee sur un dataset independant. Une evaluation sur les lignes
d'entrainement ne doit pas servir de preuve de promotion.

## Gates de promotion

La commande compare les metriques de la candidate:

- aux seuils absolus de la politique
- aux plafonds de metriques quand une valeur plus basse est meilleure
- aux metriques du champion actuel, avec une regression maximale autorisee

Les gates actuels couvrent notamment:

- volume evalue (`rows`)
- `sentiment_accuracy` et `sentiment_macro_f1`
- `theme_exact_match`, precision/recall macro et `theme_f1_macro`
- plafond `human_review_rate`

```powershell
py -3 pipelines/promote_model.py `
  --tracking-uri http://localhost:5000 `
  --dry-run
```

Promotion avec remplacement atomique des artefacts actifs:

```powershell
py -3 pipelines/promote_model.py `
  --tracking-uri http://localhost:5000 `
  --deploy-model-dir models
```

Une promotion refusee retourne un code non nul, marque la version candidate et ecrit un rapport
JSON dans `reports/model_registry/`. Une promotion acceptee conserve l'ancien champion sous
`previous_champion`.

## Rollback

```powershell
py -3 pipelines/rollback_model.py `
  --tracking-uri http://localhost:5000 `
  --deploy-model-dir models
```

Le rollback echange `champion` et `previous_champion`, redeploie les artefacts de la version
precedente et ecrit un rapport d'audit.

## DVC et MinIO

Le remote DVC `minio` est configure vers le bucket `review-insights-data`. Les credentials restent
dans `.dvc/config.local`, jamais dans Git:

```powershell
dvc remote modify --local minio access_key_id <user>
dvc remote modify --local minio secret_access_key <secret>
dvc push -r minio
```

## Critere de sortie phase 2

La phase est terminee quand:

- une candidate peut etre enregistree avec l'alias `candidate`
- une candidate insuffisante est refusee par les gates
- une candidate approuvee peut devenir `champion`
- l'ancien champion est conserve
- le rollback restaure la version precedente
- les artefacts MLflow sont stockes dans MinIO et les metadonnees dans PostgreSQL
