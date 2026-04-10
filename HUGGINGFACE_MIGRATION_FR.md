# Migration Hugging Face - Review Insights+

## Objectif

Conserver l'architecture actuelle de l'application tout en deplacant:

- les artefacts modeles hors du depot local
- l'API FastAPI vers un environnement online

## Architecture cible minimale

### 1. Model repository Hugging Face

Creer un repo modele, par exemple:

- `Francescogiraldi/review-insights-models`

Y deposer:

- `themes_clf.joblib`
- `themes_thresholds.npy`
- `sent_livraison.joblib`
- `sent_sav.joblib`
- `sent_produit.joblib`
- `manifest.json`

### 2. API repository / Space Docker

Le code applicatif courant peut etre deploye dans un Space Docker Hugging Face.

Le runtime charge alors les artefacts depuis le model repo au demarrage via:

- `MODEL_SOURCE=hf_hub`
- `HF_MODEL_REPO_ID=<repo>`

## Variables d'environnement a configurer

```env
MODEL_SOURCE=hf_hub
HF_MODEL_REPO_ID=Francescogiraldi/review-insights-models
HF_MODEL_REVISION=main
HF_TOKEN=
HF_CACHE_DIR=.cache/huggingface
HF_ARTIFACTS_DIR=.cache/review_insights/models
```

## Fichiers prepares dans le projet

- support Hugging Face Hub dans `src/review_insights/model_backend.py`
- config dans `src/review_insights/settings.py`
- variables d'environnement dans `.env.example`
- kit Space Docker dans `deploy/huggingface_api_space/`

## Etapes de migration

1. Creer le repo modele sur Hugging Face.
2. Uploader les 6 artefacts modeles.
3. Utiliser le Space Docker `Francescogiraldi/review-insights-api`.
4. Copier dans le Space:
   - `Dockerfile` depuis `deploy/huggingface_api_space/Dockerfile`
   - le code applicatif
   - `requirements.txt`
5. Configurer les variables d'environnement du Space.
6. Verifier `/health` puis `/v1/analyze`.

## Limites

- La migration preparee ici ne publie pas automatiquement sur Hugging Face depuis cette session.
- Un token ou une authentification Hugging Face sera necessaire pour uploader les artefacts dans vos repos.
