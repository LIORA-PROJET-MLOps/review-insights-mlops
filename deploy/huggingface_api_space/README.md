---
title: Review Insights API
emoji: 🚀
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# Review Insights API

Space Docker prevu pour exposer l'API FastAPI de Review Insights+.

## Repo cible

- Space: `Francescogiraldi/review-insights-api`
- Model repo: `Francescogiraldi/review-insights-models`

## Variables d'environnement attendues

- `APP_ENV=production`
- `APP_NAME=Review Insights+`
- `APP_VERSION=0.2.0`
- `MODEL_SOURCE=hf_hub`
- `HF_MODEL_REPO_ID=Francescogiraldi/review-insights-models`
- `HF_MODEL_REVISION=main`
- `HF_TOKEN=<token-hf-si-repo-prive>`
- `HF_CACHE_DIR=/data/huggingface`
- `HF_ARTIFACTS_DIR=/data/review_insights/models`
- `API_KEY=<optionnel>`
- `TRUSTED_HOSTS=*`
- `ALLOWED_ORIGINS=*`

## Ports

- Le conteneur expose `7860` pour etre compatible avec Hugging Face Spaces.
