# Setup du Space Hugging Face API

## Space cible

- `Francescogiraldi/review-insights-api`

## Methode recommandee

1. Generer localement le bundle:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_hf_space_bundle.ps1
```

2. Recuperer le dossier genere:

- `dist/hf_space_api_bundle`

3. Copier son contenu a la racine du Space Hugging Face.

## Fichiers attendus a la racine du Space

- `README.md`
- `Dockerfile`
- `.dockerignore`
- `requirements.txt`
- `api_app.py`
- `src/review_insights/...`

## Variables d'environnement a configurer dans le Space

```env
APP_ENV=production
APP_NAME=Review Insights+
APP_VERSION=1.0.0
MODEL_SOURCE=hf_hub
HF_MODEL_REPO_ID=Francescogiraldi/review-insights-models
HF_MODEL_REVISION=1d6a5bd3e653ba75b6c8fed614e156d1a3c73779
HF_TOKEN=
HF_CACHE_DIR=/data/huggingface
HF_ARTIFACTS_DIR=/data/review_insights/models
API_KEY=
TRUSTED_HOSTS=*
ALLOWED_ORIGINS=*
ENABLE_DOCS=true
```

## Verification apres build

Verifier dans le Space:

- `/health`
- `/docs`
- `/v1/analyze`
