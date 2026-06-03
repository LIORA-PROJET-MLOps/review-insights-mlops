# Livrables finaux et preuves dans le depot

## Livrables techniques

- Application Streamlit de demonstration: `app.py`
- Client HTTP Streamlit: `src/review_insights/api_client.py`
- API FastAPI: `api_app.py` et `src/review_insights/api.py`
- Service metier: `src/review_insights/service.py`
- Backend modeles reels: `src/review_insights/model_backend.py`
- Monitoring: `src/review_insights/monitoring.py`
- Evaluation: `src/review_insights/evaluation.py`
- Reporting: `src/review_insights/reporting.py`

## Livrables MLOps

- Artefacts modeles: `models/`
- Manifest d'artefacts: `models/manifest.json`
- Contrat data: `data/contracts/reviews_v1.json`
- Pipeline ingestion avec quarantaine, checksums et splits: `src/review_insights/data_store.py`
- Pipeline evaluation: `pipelines/evaluate_default.py`
- Pipeline training reproductible: `pipelines/train_models.py`
- Placeholder training historique: `pipelines/train_placeholder.py`
- Rapports generes: `reports/default_evaluation.json` et `reports/default_evaluation.md`
- Placeholder artifact training: `artifacts/TRAINING_PLACEHOLDER.md`

## Livrables exploitation

- Containerisation: `Dockerfile`
- Orchestration locale: `compose.yaml`
- Configuration: `.env.example`
- CI: `.github/workflows/ci.yml`
- Bundles Hugging Face reproductibles: `scripts/build_hf_space_bundle.ps1` et `scripts/build_hf_frontend_space_bundle.ps1`

## Livrables documentation

- Vue d'ensemble du projet: `README.md`
- Alignement kickoff MLOps: `PROJECT_MLOPS_GUIDE_FR.md`
- Securite et exploitation: `docs/SECURITE_EXPLOITATION_FR.md`
- Livrables finaux: `docs/LIVRABLES_FINAUX_FR.md`
- Dossier soutenance: `docs/SOUTENANCE_READY_FR.md`
- Etat des lieux et plan final: `docs/ETAT_DES_LIEUX_PLAN_PHASE_FINALE_FR.md`
