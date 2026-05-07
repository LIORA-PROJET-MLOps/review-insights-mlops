# Guide final MLOps - Review Insights+

## Objectif

Ce document formalise la version finale cible du POC selon la logique du kickoff MLOps Liora:

- documentation et cadrage en francais
- application de demonstration orientee commentaires en anglais
- structure de projet reproductible
- separation claire entre interface, service, inference, evaluation et monitoring

## Alignement avec les phases du kickoff

### Phase 1 - Fondations

Objectifs couverts:

- structure de code claire et modulaire
- environnement applicatif definissable par configuration
- documentation de lancement et de verification
- base de tests automatises
- API et interface de demonstration

Elements deja presents:

- `src/review_insights/`
- `requirements.txt`
- `pyproject.toml`
- `README.md`
- `tests/`
- `app.py`
- `api_app.py`

### Phase 2 - Microservices et versioning

Objectifs couverts partiellement:

- separation entre frontend et backend d'inference
- artefacts modeles versionnables
- manifest d'artefacts
- backend reel avec fallback
- parametrage runtime par variables d'environnement

Elements deja presents:

- service central `ReviewAnalysisService`
- API REST FastAPI
- dossier `models/`
- `models/manifest.json`

### Phase 3 - Orchestration et deploiement

Objectifs prepares:

- application executable via API ou Streamlit
- containerisation initiale
- orchestration locale simple
- healthcheck API
- contrats d'E/S stabilises
- verification automatique par CI

Elements deja presents:

- `Dockerfile`
- `compose.yaml`
- endpoint `/health`
- endpoint `/v1/analyze`
- scripts `pipelines/evaluate_default.py`, `pipelines/train_models.py` et `pipelines/train_placeholder.py`
- generation d'artefacts dans `reports/` et `artifacts/`
- workflow `.github/workflows/ci.yml`

### Phase 4 - Monitoring et maintenance

Objectifs couverts en base:

- compteurs runtime d'inference
- taux de revue humaine
- distribution des sentiments
- distribution des themes
- endpoint de metrics
- endpoint d'evaluation offline sur dataset par defaut

Elements deja presents:

- endpoint `/metrics`
- endpoint `/v1/evaluate/default`
- module `monitoring.py`
- module `evaluation.py`
- module `reporting.py`
- rapports d'evaluation exportes en JSON et Markdown

## Securite et gouvernance technique

Elements ajoutes dans la base finale:

- protection optionnelle des endpoints par cle API
- filtrage des hotes via `TRUSTED_HOSTS`
- configuration CORS
- headers de securite HTTP
- limite configurable sur la taille des reviews

## Architecture logique finale du POC

```text
Review text
   |
   v
API REST / Streamlit
   |
   v
ReviewAnalysisService
   |
   +--> backend real models (project_models_v1)
   |
   +--> fallback heuristic backend
   |
   +--> monitoring runtime
   |
   +--> evaluation batch
```

## Principes retenus

- Le frontend ne porte pas la logique modele.
- Le service central reste l'unique point d'entree metier.
- Les schemas API stabilisent les contrats.
- Les artefacts modeles sont versionnables et declaratifs.
- Le monitoring est expose separement de l'inference.
- L'evaluation offline est disponible sans refaire l'architecture.

## Limites actuelles

- Les modeles de sentiment embarquent maintenant un mapping de classes explicite dans `models/manifest.json`.
- Les artefacts `joblib` ont une sensibilite de version `scikit-learn`.
- La pipeline d'entrainement existe sur le dataset de demonstration, mais le retraining automatise reste a industrialiser.
- Le monitoring est applicatif mais pas encore branche a Prometheus/Grafana.

## Resultat observable sur la base finale

- Backend reel actif: `project_models_v1`
- Evaluation offline disponible depuis le depot
- Rapport JSON: `reports/default_evaluation.json`
- Rapport Markdown: `reports/default_evaluation.md`
- Pipeline training reproductible: `pipelines/train_models.py`
- Placeholder historique: `artifacts/TRAINING_PLACEHOLDER.md`
- Score observe sur le dataset de demonstration:
- `sentiment_accuracy = 0.75`
- `theme_exact_match = 1.0`
- `theme_precision_macro = 1.0`
- `theme_recall_macro = 1.0`

## Etapes recommandees pour la suite

1. Ajouter une evaluation batch sur un vrai dataset de validation.
2. Ajouter promotion MLflow Model Registry pour les runs valides.
3. Exposer des metrics compatibles Prometheus.
4. Ajouter une logique de retraining et de drift monitoring.
5. Figer les versions exactes des dependances de training et runtime.
6. Dockeriser aussi le frontend Streamlit ou le servir derriere un reverse proxy.
