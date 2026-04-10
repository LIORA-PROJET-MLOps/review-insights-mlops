# Hugging Face Model Repo - Review Insights+

## Repo cible

- `Francescogiraldi/review-insights-models`

## Fichiers a uploader

- `models/themes_clf.joblib`
- `models/themes_thresholds.npy`
- `models/sent_livraison.joblib`
- `models/sent_sav.joblib`
- `models/sent_produit.joblib`
- `models/manifest.json`

## Noms finaux attendus dans le repo Hugging Face

- `themes_clf.joblib`
- `themes_thresholds.npy`
- `sent_livraison.joblib`
- `sent_sav.joblib`
- `sent_produit.joblib`
- `manifest.json`

## Verification apres upload

Le backend FastAPI en mode `hf_hub` s'attend a retrouver exactement ces 6 fichiers a la racine du repo modele.

## Config utilisee par l'application

```env
MODEL_SOURCE=hf_hub
HF_MODEL_REPO_ID=Francescogiraldi/review-insights-models
HF_MODEL_REVISION=main
```
