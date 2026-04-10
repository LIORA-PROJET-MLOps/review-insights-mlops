# Setup Hugging Face Space Frontend

## Objectif

Ce Space sert l'interface web complete de `Review Insights+` et consomme l'API online deja deployee.

## Repo recommande

- `Francescogiraldi/review-insights-frontend`

## Contenu a publier

Publier le contenu du dossier:

- `dist/hf_space_frontend_bundle`

## Pages disponibles

- `index.html` : landing produit
- `app-online.html` : console frontend complete
- `demo-api.html` : mini test API

## API cible par defaut

Le frontend vise par defaut:

- `https://francescogiraldi-review-insights-api.hf.space`

## Remarques

- aucun secret n'est requis si l'API reste publique
- si une cle API est activee cote backend, elle peut etre saisie directement dans l'interface
