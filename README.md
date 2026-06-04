# Review Insights+ - base finale POC/MVP MLOps

## Vue d'ensemble

Ce depot contient une base finale de POC/MVP alignee avec les lignes guides du projet MLOps Liora:

- cadrage produit et documentation en francais
- application de demonstration pour commentaires en anglais
- architecture modulaire et reproductible
- version "production-shaped" avec API, frontend, evaluation et monitoring

## Ce que couvre la version finale

### Fondations

- structure de code modulaire
- configuration centralisee
- tests automatises
- documentation de lancement

### Microservices et versioning

- separation frontend Streamlit / service / API
- artefacts modeles versionnables dans `models/`
- manifest d'artefacts
- configuration centralisee par variables d'environnement
- support des artefacts distants via Hugging Face Hub

### Orchestration et deploiement

- API REST FastAPI
- point d'entree Streamlit
- `Dockerfile`
- `compose.yaml`
- healthcheck
- scripts `pipelines/` executables depuis le depot
- CI GitHub Actions

### Monitoring et maintenance

- endpoint `/metrics`
- endpoint `/v1/evaluate/default`
- suivi des experiences avec MLflow
- suivi du volume de requetes
- suivi du taux de revue humaine
- distributions des predictions
- metriques HTTP, taux d'erreur et `X-Request-ID`
- rapports exportables dans `reports/`

### Securite et exploitation

- protection optionnelle par cle API
- `TrustedHostMiddleware`
- configuration CORS
- headers HTTP de securite
- taille maximale de payload configurable

## Backend d'inference

Le service utilise automatiquement:

- `project_models_v1` si les artefacts du projet sont presents dans `models/`
- `heuristic_rules_v1` sinon

Le chargement des artefacts peut aussi etre fait depuis Hugging Face Hub avec:

- `MODEL_SOURCE=hf_hub`
- `HF_MODEL_REPO_ID=<repo-modele>`

Artefacts modeles attendus:

- `themes_clf.joblib`
- `themes_thresholds.npy`
- `sent_livraison.joblib`
- `sent_sav.joblib`
- `sent_produit.joblib`

Le backend reel est branche sans changer l'architecture applicative: seule la couche service choisit le moteur approprie.

## Structure

```text
.
|-- .env.example
|-- api_app.py
|-- app.py
|-- Dockerfile
|-- docs/
|-- artifacts/
|-- models/
|   `-- manifest.json
|-- pipelines/
|   |-- evaluate_default.py
|   |-- train_models.py
|   `-- train_placeholder.py
|-- PROJECT_MLOPS_GUIDE_FR.md
|-- pyproject.toml
|-- requirements.txt
|-- reports/
|-- compose.yaml
|-- src/
|   `-- review_insights/
|       |-- api.py
|       |-- app.py
|       |-- config.py
|       |-- dataset.py
|       |-- engine.py
|       |-- evaluation.py
|       |-- mlflow_tracking.py
|       |-- model_backend.py
|       |-- monitoring.py
|       |-- schemas.py
|       |-- service.py
|       `-- settings.py
`-- tests/
    |-- test_api.py
    |-- test_engine.py
    `-- test_service.py
```

## Lancer l'application

### Frontend Streamlit

```bash
pip install -r requirements-frontend.txt
streamlit run app.py
```

Le frontend Streamlit est un client des services `api`, `data` et `monitoring`. Pour un lancement
complet, utiliser `docker compose up --build` ou demarrer les trois services avant Streamlit.

## Pipeline data locale et retraining

Le POC peut maintenant utiliser des CSV comme source d'alimentation tout en les stockant dans une structure locale versionnee:

```text
data/
|-- raw/
|   |-- incoming/
|   `-- archive/
|-- processed/
|-- validated/
|-- quarantine/
|-- splits/
|-- contracts/
|-- registry/
`-- sample/
```

Les fichiers generes dans `raw/`, `processed/`, `validated`, `quarantine`, `splits` et `registry`
sont ignores par Git, sauf les placeholders. Le contrat versionne est disponible dans
`data/contracts/reviews_v1.json` et la politique de qualite staging dans
`data/contracts/reviews_quality_policy_v1.json`.

Colonnes attendues pour un dataset d'entrainement:

- `review_id`
- `review_title`
- `review_body`
- `sentiment_label`
- `theme_livraison`
- `theme_sav`
- `theme_produit`

Ingestion d'un CSV:

```bash
py -3 pipelines/ingest_csv_dataset.py data/sample/reviews_sample.csv
```

La commande archive le brut, ecrit des versions CSV de compatibilite et Parquet canoniques, place
les lignes rejetees en quarantaine, cree une file d'annotation pour les sentiments par theme
manquants, genere des splits deterministes quand le volume le permet, calcule les checksums et
ajoute un manifest et un rapport de qualite dans `data/registry/`.

Le manifest distingue un dataset techniquement valide d'un dataset pret pour un entrainement
partage. Pour bloquer le retraining quand les gates staging ne passent pas:

```powershell
py -3 pipelines/ingest_csv_dataset.py data/sample/reviews_poc_test.csv `
  --dataset-version candidate_v1 `
  --enforce-quality-gates
```

Le dataset POC de 40 reviews est volontairement `not_ready`: il manque de volume et ne contient pas
encore les labels de sentiment explicites par theme. Les labels ne sont jamais inventes.

Retraining depuis un dataset valide, de preference avec le Parquet canonique:

```bash
py -3 pipelines/train_models.py --dataset-path data/validated/training_dataset_<version>.parquet
```

Pour fournir un jeu d'evaluation independant:

```powershell
py -3 pipelines/train_models.py `
  --dataset-path data/splits/<version>/train.parquet `
  --evaluation-dataset-path data/splits/<version>/test.parquet
```

Sans `--dataset-path`, la pipeline entraine sur le dataset de demonstration integre et evalue sur
`data/sample/reviews_poc_test.csv`, qui contient 40 reviews distinctes.

Commande combinee ingestion + retraining:

```bash
py -3 pipelines/ingest_and_retrain.py data/sample/reviews_poc_test.csv --dataset-version poc_test_40
```

Cette commande fait en une seule execution:

- ingestion du CSV source
- archive du brut
- ecriture du dataset nettoye
- ecriture de la quarantaine et des manifests de qualite
- ecriture du dataset valide pour training
- generation de splits train / validation / test quand le volume le permet
- retraining des artefacts modele
- evaluation sur le split test, jamais sur les lignes d'entrainement
- sortie JSON avec chemins data, checksums et `artifacts/trained_models_<version>/...`

### Versionnement DVC

DVC est initialise avec un remote local de developpement `localstore`. L'artefact canonique
`data/validated/training_dataset_poc_reference_v1.parquet` est suivi par son fichier `.dvc`.

```powershell
py -3 -m pip install -r requirements-data-versioning.txt
dvc status
dvc push
dvc pull
```

Pour un environnement partage, remplacer le remote par un bucket S3 ou un endpoint compatible S3
et conserver les credentials uniquement dans `.dvc/config.local` avec `dvc remote modify --local`.
Le workflow complet est documente dans `docs/DATA_GOVERNANCE_FR.md`.

### Tracking training et MLflow Model Registry

Le retraining peut aussi creer un run MLflow et enregistrer une version candidate dans le Model Registry.

Pre-requis local:

```bash
pip install -r requirements-data.txt
docker compose up -d mlflow
```

Variables d'environnement PowerShell:

```powershell
$env:MLFLOW_TRACKING_ENABLED="true"
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
$env:MLFLOW_EXPERIMENT_NAME="review-insights-training"
```

Commande:

```bash
py -3 pipelines/train_models.py --dataset-path data/validated/training_dataset_<version>.csv --mlflow-log --register-model
```

Commande combinee ingestion + retraining + registry:

```bash
py -3 pipelines/ingest_and_retrain.py data/sample/reviews_poc_test.csv --dataset-version poc_test_40 --mlflow-log --register-model
```

Effets attendus:

- creation d'un run MLflow de training
- logging des metriques `sentiment_accuracy`, `sentiment_macro_f1`, `theme_exact_match`, `theme_precision_macro`, `theme_recall_macro`, `theme_f1_macro` et `human_review_rate`
- logging des artefacts `joblib`, seuils et manifest
- creation d'une version candidate dans le registered model `review-insights-project-models`

Le registry utilise les alias `candidate`, `champion` et `previous_champion`. La promotion reste
volontaire et applique les gates versionnees de `config/model_promotion_policy_v1.json`.

Dry-run de promotion:

```powershell
py -3 pipelines/promote_model.py --tracking-uri http://localhost:5000 --dry-run
```

Promotion et deploiement atomique vers les artefacts actifs:

```powershell
py -3 pipelines/promote_model.py --tracking-uri http://localhost:5000 --deploy-model-dir models
```

Rollback:

```powershell
py -3 pipelines/rollback_model.py --tracking-uri http://localhost:5000 --deploy-model-dir models
```

Le runbook complet est disponible dans `docs/MODEL_GOVERNANCE_FR.md`.

### API

```bash
pip install -r requirements.txt
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

### Orchestration locale

```bash
docker compose up --build
```

Services exposes:

- API inference: `http://localhost:8000`
- Data service: `http://localhost:8001`
- MLflow tracking UI: `http://localhost:5000`
- MinIO API et console: `http://localhost:9100` et `http://localhost:9101`
- Monitoring gateway and Prometheus text metrics: `http://localhost:9000`
- Frontend Streamlit: `http://localhost:8501`

### Build Docker recommande

Sur Docker Desktop Windows, preferer un build progressif quand le cache est vide ou apres une purge:

```bash
docker compose build monitoring
docker compose build api
docker compose build data
docker compose build mlflow
docker compose build streamlit
docker compose up -d
```

Validation rapide:

```bash
docker compose ps
```

Endpoints a verifier:

- `http://localhost:8000/health`
- `http://localhost:8001/health`
- `http://localhost:5000/health`
- `http://localhost:9000/health`
- `http://localhost:8501`

Si Docker Desktop affiche ponctuellement `EOF` ou `502 Bad Gateway` pendant un build, verifier d'abord l'etat reel:

```bash
docker images
docker compose ps
docker system df
```

Ces erreurs peuvent venir de Docker Desktop / BuildKit pendant l'export d'image ou le controle des healthchecks. Si l'image existe et que les containers sont `healthy`, l'application peut etre correcte. En cas de stockage Docker instable ou cache corrompu:

```bash
docker compose down
docker system prune -a --volumes -f
docker builder prune -af
docker buildx history rm --all
```

Puis relancer le build service par service.

## Architecture microservices Docker

Le projet est maintenant separe en services Docker specialises:

- `api`: service FastAPI d'inference, expose `/health`, `/v1/analyze`, `/metrics` et `/v1/evaluate/default`.
- `data`: service FastAPI data/evaluation, expose le dataset de demonstration via `/v1/datasets/default`, son profil via `/v1/datasets/default/profile` et l'evaluation de reference sur 40 reviews via `/v1/evaluate/default`.
- `postgres`: stockage des metadonnees MLflow.
- `minio` et `minio-init`: stockage objet des artefacts MLflow et des datasets DVC.
- `mlflow`: serveur de tracking et Model Registry, expose l'interface MLflow sur `http://localhost:5000`.
- `monitoring`: gateway de supervision, interroge l'API interne, expose `/v1/api/health`, `/v1/api/metrics` et `/metrics` au format texte compatible Prometheus.
- `streamlit`: frontend POC client des services `api`, `data` et `monitoring`, sans chargement local des modeles.

Dockerfiles:

```text
docker/
|-- api/Dockerfile
|-- data/Dockerfile
|-- frontend/Dockerfile
|-- mlflow/Dockerfile
`-- monitoring/Dockerfile
```

Dependencies are split by runtime surface:

- `requirements-api.txt`: FastAPI inference service and model loading.
- `requirements-data.txt`: dataset profile/evaluation service, offline pipelines and MLflow client logging.
- `requirements-mlflow.txt`: MLflow tracking server runtime.
- `requirements-monitoring.txt`: lightweight monitoring gateway.
- `requirements-frontend.txt`: Streamlit frontend runtime.
- `requirements-dev.txt`: local development/test dependencies.

Volumes:

- `./models:/app/models:ro` garde les artefacts modeles montes en lecture seule dans les services qui inferent.
- `reports` et `artifacts` isolent les sorties du service data/pipelines.
- `mlflow_postgres_data` conserve les metadonnees MLflow.
- `minio_data` conserve les artefacts MLflow et les objets DVC.

### Evaluation offline

```bash
py -3 pipelines/evaluate_default.py
```

Sorties generees:

- `reports/default_evaluation.json`
- `reports/default_evaluation.md`

Si `MLFLOW_TRACKING_ENABLED=true`, le script logge aussi dans MLflow:

- parametres: backend modele et dataset
- metriques: lignes, accuracy sentiment, exact match theme, precision/recall macro
- artefacts JSON/Markdown
- artefacts modele sous le chemin MLflow `model/` quand le package `mlflow` est installe dans le runtime

### MLflow tracking

En Docker Compose, MLflow est lance automatiquement:

```bash
docker compose up --build mlflow data
```

Pour forcer une evaluation fonctionnelle et verifier que MLflow recoit bien un run:

```bash
MLFLOW_TRACKING_ENABLED=true MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_EXPERIMENT_NAME=review-insights-default py -3 pipelines/evaluate_default.py
```

Sur PowerShell:

```powershell
$env:MLFLOW_TRACKING_ENABLED="true"
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
$env:MLFLOW_EXPERIMENT_NAME="review-insights-default"
py -3 pipelines/evaluate_default.py
```

La sortie attendue doit inclure:

```text
MLflow tracking: logged (http://localhost:5000)
MLflow run id: ...
MLflow model artifacts: logged
```

Interface:

- `http://localhost:5000`

Configuration utile:

```env
MLFLOW_TRACKING_ENABLED=true
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=review-insights-default
```

Dans Compose, le service `data` utilise `http://mlflow:5000` et embarque le client `mlflow` pour uploader les artefacts modele dans le run. En local hors Docker, installer aussi `requirements-mlflow.txt` si l'environnement courant ne contient pas encore le package `mlflow`.

Important: cette version journalise les artefacts modele dans les runs MLflow, enregistre les
candidates dans le Model Registry, applique des gates de promotion avec seuils minimums et plafonds
de metriques, puis conserve un rollback via les alias `champion` et `previous_champion`.

### Pipeline d'entrainement reproductible

La pipeline `pipelines/train_models.py` entraine les artefacts attendus par le backend `project_models_v1` depuis le dataset par defaut. Par securite, elle ecrit dans `artifacts/trained_models/` par defaut et ne remplace pas les modeles actifs.

```bash
py -3 pipelines/train_models.py
```

Pour promouvoir explicitement les nouveaux artefacts comme modeles actifs:

```bash
py -3 pipelines/train_models.py --output-dir models
```

Artefacts generes:

- `themes_clf.joblib`
- `themes_thresholds.npy`
- `sent_livraison.joblib`
- `sent_sav.joblib`
- `sent_produit.joblib`
- `manifest.json`

### Placeholder historique d'entrainement

```bash
py -3 pipelines/train_placeholder.py
```

Sortie generee:

- `artifacts/TRAINING_PLACEHOLDER.md`

## Endpoints disponibles

### `GET /health`

Retourne:

- statut applicatif
- environnement
- version applicative
- backend d'inference actif
- source modele active (`local` ou `hf_hub`)
- revision modele et version du jeu d'artefacts
- presence du manifest modele
- activation ou non de la protection des endpoints
- profil securite (`local_relaxed`, `needs_hardening`, `staging_ready`, etc.)
- warnings de configuration (`wildcard_cors`, `docs_enabled`, `api_key_not_required`, etc.)
- erreur de chargement modele si le backend reel bascule sur le fallback heuristique

### Securite API

Par defaut, la cle API reste optionnelle pour faciliter le developpement local. Pour un environnement partage, staging ou production, activer:

```env
REQUIRE_API_KEY=true
API_KEY=change-me-with-a-long-secret
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
ALLOWED_ORIGINS=https://votre-frontend.example
TRUSTED_HOSTS=votre-api.example
ENABLE_DOCS=false
```

Endpoints proteges quand `REQUIRE_API_KEY=true` ou quand `API_KEY` est configuree:

- `POST /v1/analyze`
- `GET /metrics`
- `GET /v1/evaluate/default`
- endpoints sensibles des services `data` et `monitoring`

Endpoint public:

- `GET /health`

Exemple d'appel protege:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/v1/analyze" `
  -Method Post `
  -Headers @{ "X-API-Key" = "change-me-with-a-long-secret" } `
  -ContentType "application/json" `
  -Body '{"review_id":"secure_test","review_text":"fast delivery and great product"}'
```

Comportements attendus:

- `401 Unauthorized`: cle absente ou invalide.
- `429 Too Many Requests`: rate limit depasse.
- `503 Service Unavailable`: `REQUIRE_API_KEY=true` mais `API_KEY` non configuree.

Le rate limit est en memoire et s'applique par cle API, sinon par IP client. Pour une production multi-replicas, il faudra le remplacer par un stockage partage type Redis.

### `POST /v1/analyze`

Analyse une review individuelle.

### `GET /metrics`

Retourne les metriques runtime:

- nombre total de requetes
- nombre et taux de revue humaine
- latence d'inference moyenne, p50 et p95
- distribution des sentiments
- distribution des themes
- distribution des backends
- volume HTTP, taux d'erreur 5xx, latence HTTP p50/p95
- distribution des statuts et endpoints HTTP

### `GET /v1/evaluate/default`

Lance une evaluation offline sur le dataset de reference `data/sample/reviews_poc_test.csv`.

Metriques calculees:

- `sentiment_accuracy`
- `sentiment_macro_precision`
- `sentiment_macro_recall`
- `sentiment_macro_f1`
- `sentiment_per_class`
- `sentiment_confusion_matrix`
- `theme_exact_match`
- `theme_precision_macro`
- `theme_recall_macro`
- `theme_f1_macro`
- `theme_metrics`
- `human_review_rate`

## Verification locale

```bash
pytest
```

Etat verifie sur cette base:

- `65 passed`
- couverture globale: `78.04%`
- lint Ruff: propre
- cinq services Docker Compose construits et verifies
- bundle Hugging Face API reconstruit et charge depuis une revision immuable
- rapport offline genere avec `project_models_v1`
- metriques observees sur les 40 reviews de reference:
- `sentiment_accuracy = 0.575`
- `sentiment_macro_f1 = 0.5111`
- `theme_exact_match = 0.675`
- `theme_precision_macro = 0.8787`
- `theme_recall_macro = 0.8972`
- `theme_f1_macro = 0.8877`
- `human_review_rate = 0.5`

## Limites connues

- les modeles de sentiment embarquent maintenant un mapping de classes versionne dans `models/manifest.json`
- les artefacts actifs embarquent des checksums SHA-256 verifies au chargement
- le fallback par calibration reste disponible si un manifest externe est incomplet
- compatibilite scikit-learn liee a la version de serialisation des artefacts
- les labels de sentiment par theme explicites sont supportes; en leur absence, le training utilise le sentiment global uniquement sur les reviews ou le theme est present
- le stockage objet partage, Grafana/alertes et le drift monitoring restent a industrialiser

## Documents projet

- [README.md](README.md)
- [PROJECT_MLOPS_GUIDE_FR.md](PROJECT_MLOPS_GUIDE_FR.md)
- [ETAT_DES_LIEUX_PLAN_PHASE_FINALE_FR.md](docs/ETAT_DES_LIEUX_PLAN_PHASE_FINALE_FR.md)
- [DATA_GOVERNANCE_FR.md](docs/DATA_GOVERNANCE_FR.md)
- [MODEL_GOVERNANCE_FR.md](docs/MODEL_GOVERNANCE_FR.md)
- [SECURITE_EXPLOITATION_FR.md](docs/SECURITE_EXPLOITATION_FR.md)
- [LIVRABLES_FINAUX_FR.md](docs/LIVRABLES_FINAUX_FR.md)
- [SOUTENANCE_READY_FR.md](docs/SOUTENANCE_READY_FR.md)
- [HUGGINGFACE_MIGRATION_FR.md](HUGGINGFACE_MIGRATION_FR.md)

## GitHub Pages

Une page de presentation interactive en francais est prete dans `site/`.

- entree statique: `site/index.html`
- styles: `site/styles.css`
- interactions: `site/script.js`
- application web online: `site/app-online.html`
- styles app: `site/app.css`
- logique app: `site/app.js`
- mini demo API online: `site/demo-api.html`
- deploiement: `.github/workflows/pages.yml`

## Frontend et backend online

Une architecture online complete est maintenant preparee:

- backend API HF: `Francescogiraldi/review-insights-api`
- model repo HF: `Francescogiraldi/review-insights-models`
- frontend HF: `Francescogiraldi/review-insights-frontend`
- bundle frontend HF: `dist/hf_space_frontend_bundle`
- bundle backend HF: `dist/hf_space_api_bundle`

Scripts de generation:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\build_hf_space_bundle.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build_hf_frontend_space_bundle.ps1
```

## Suite recommandee

1. Collecter et annoter un dataset projet qui passe les gates de `reviews_quality_policy_v1.json`.
2. Ajouter l'orchestration Airflow des pipelines deja fiables.
3. Ajouter Grafana, alerting et drift monitoring.
