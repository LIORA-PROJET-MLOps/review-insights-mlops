# Tests fonctionnels Review Insights+

## Objectif

Ce protocole teste les principales fonctionnalites du POC lance en Docker Compose:

- healthchecks API/data/monitoring;
- analyse unitaire;
- batch de reviews depuis un CSV de test;
- profil dataset;
- evaluation offline;
- feedback humain;
- metriques JSON API;
- export Prometheus;
- frontend Streamlit;
- pipelines CLI annotation/release.

## Dataset de test

Le CSV fonctionnel est:

```text
data/sample/reviews_functional_test.csv
```

Il contient des cas couvrant:

- livraison positive et negative;
- support/SAV positif et negatif;
- produit positif, negatif et neutre;
- reviews multi-themes;
- review sans theme metier clair;
- labels explicites `sentiment_livraison`, `sentiment_sav`, `sentiment_produit`.

## Pre-requis

Depuis le dossier du projet:

```powershell
git pull
docker compose up -d --build
docker compose ps
```

Attendre que les services soient `healthy` ou joignables:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:9000/health
```

## Lancer tout le smoke test

Sur la machine qui execute Docker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_functional_smoke_tests.ps1
```

Si le frontend Streamlit n'est pas lance:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_functional_smoke_tests.ps1 -SkipFrontend
```

Si les pipelines CLI ne doivent pas etre relances:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_functional_smoke_tests.ps1 -SkipPipelines
```

## Avec API key

Si `REQUIRE_API_KEY=true` ou `API_KEY` est configuree:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_functional_smoke_tests.ps1 `
  -ApiKey "votre-cle-api"
```

## Depuis un autre PC

Remplacer `localhost` par l'IP de la machine Docker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_functional_smoke_tests.ps1 `
  -ApiBase "http://IP_DE_BENJAMIN:8000" `
  -DataBase "http://IP_DE_BENJAMIN:8001" `
  -MonitoringBase "http://IP_DE_BENJAMIN:9000" `
  -FrontendBase "http://IP_DE_BENJAMIN:8501"
```

Les ports doivent etre autorises par le firewall Windows de la machine Docker.

## Tests manuels utiles

Analyse unitaire:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/v1/analyze" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"review_id":"manual_test","review_text":"customer support never answered and the refund process was slow"}'
```

Profil data:

```powershell
Invoke-RestMethod http://localhost:8001/v1/datasets/default/profile
```

Evaluation complete:

```powershell
Invoke-RestMethod http://localhost:8001/v1/evaluate/default | ConvertTo-Json -Depth 10
```

Feedback humain:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8001/v1/feedback" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"review_id":"manual_test","theme":"sav","corrected_theme_present":1,"corrected_sentiment":"negative","reviewer":"qa"}'
```

Metriques Prometheus:

```powershell
curl.exe http://localhost:9000/metrics
```

## Resultat attendu

Le script doit finir par:

```text
Functional smoke tests passed.
```

Les sorties attendues incluent:

- `API backend: project_models_v1` ou fallback documente;
- au moins un theme `sav` detecte sur la review support;
- `Evaluation rows = 40`;
- `sentiment_macro_f1` et `theme_f1_macro` presents;
- feedback humain enregistre;
- metriques Prometheus contenant `review_insights_requests_total`;
- frontend HTTP 200 si Streamlit est lance.
