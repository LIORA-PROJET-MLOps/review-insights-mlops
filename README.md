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
- suivi du volume de requetes
- suivi du taux de revue humaine
- distributions des predictions
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
pip install -r requirements.txt
streamlit run app.py
```

### API

```bash
pip install -r requirements.txt
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

### Orchestration locale

```bash
docker compose up --build
```

### Evaluation offline

```bash
py -3 pipelines/evaluate_default.py
```

Sorties generees:

- `reports/default_evaluation.json`
- `reports/default_evaluation.md`

### Placeholder pipeline d'entrainement

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
- presence du manifest modele
- activation ou non de la protection des endpoints

### `POST /v1/analyze`

Analyse une review individuelle.

### `GET /metrics`

Retourne les metriques runtime:

- nombre total de requetes
- nombre et taux de revue humaine
- distribution des sentiments
- distribution des themes
- distribution des backends

### `GET /v1/evaluate/default`

Lance une evaluation offline sur le dataset de demonstration.

Metriques calculees:

- `sentiment_accuracy`
- `theme_exact_match`
- `theme_precision_macro`
- `theme_recall_macro`

## Verification locale

```bash
pytest
```

Etat verifie sur cette base:

- `11 passed`
- rapport offline genere avec `project_models_v1`
- metriques observees sur dataset demo:
- `sentiment_accuracy = 0.75`
- `theme_exact_match = 1.0`
- `theme_precision_macro = 1.0`
- `theme_recall_macro = 1.0`

## Limites connues

- les modeles de sentiment n'embarquent pas un mapping de classes versionne
- ce mapping est reconstruit par calibration au chargement
- compatibilite scikit-learn liee a la version de serialisation des artefacts
- pas encore de pipeline d'entrainement/retraining dans ce depot

## Documents projet

- [README.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\README.md)
- [PROJECT_MLOPS_GUIDE_FR.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\PROJECT_MLOPS_GUIDE_FR.md)
- [SECURITE_EXPLOITATION_FR.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\docs\SECURITE_EXPLOITATION_FR.md)
- [LIVRABLES_FINAUX_FR.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\docs\LIVRABLES_FINAUX_FR.md)
- [SOUTENANCE_READY_FR.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\docs\SOUTENANCE_READY_FR.md)
- [HUGGINGFACE_MIGRATION_FR.md](C:\Users\franc_ppcp5lu\Documents\New%20project%202\HUGGINGFACE_MIGRATION_FR.md)

## GitHub Pages

Une page de presentation interactive en francais est prete dans `site/`.

- entree statique: `site/index.html`
- styles: `site/styles.css`
- interactions: `site/script.js`
- deploiement: `.github/workflows/pages.yml`

## Suite recommandee

1. Ajouter un pipeline d'entrainement versionne.
2. Ajouter une vraie evaluation sur un dataset de validation projet.
3. Exposer des metriques compatibles Prometheus.
4. Ajouter versionnement de donnees/modeles et logique de retraining.
