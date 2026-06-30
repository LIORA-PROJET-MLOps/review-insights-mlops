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
- `APP_VERSION=1.0.0`
- `MODEL_SOURCE=hf_hub`
- `HF_MODEL_REPO_ID=Francescogiraldi/review-insights-models`
- `HF_MODEL_REVISION=1d6a5bd3e653ba75b6c8fed614e156d1a3c73779`
- `HF_TOKEN=<token-hf-si-repo-prive>`
- `HF_CACHE_DIR=/data/huggingface`
- `HF_ARTIFACTS_DIR=/data/review_insights/models`
- `SENTIMENT_BACKEND=project` ou `hf_onnx` apres validation du benchmark
- `HF_SENTIMENT_MODEL_ID=SebasLopez-ai/distilbert-amazon-reviews-sentiment`
- `HF_SENTIMENT_REVISION=881c6455b01b7ef50026f33902f6433651a1b1f0`
- `HF_SENTIMENT_ARTIFACTS_DIR=/data/review_insights/sentiment`
- `API_KEY=<optionnel>`
- `TRUSTED_HOSTS=*`
- `ALLOWED_ORIGINS=*`

## Ports

- Le conteneur expose `7860` pour etre compatible avec Hugging Face Spaces.
