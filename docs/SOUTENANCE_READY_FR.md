# Dossier soutenance ready

## Message central

Review Insights+ est un POC/MVP NLP pour analyser des avis Trustpilot en anglais, structure selon une logique MLOps complete:

- architecture modulaire
- modeles reels branches
- API et interface de demonstration
- evaluation offline
- monitoring runtime
- base CI/CD et deploiement

## Plan conseille pour la soutenance

1. Contexte business et problematique Trustpilot.
2. MVP cible et utilisateurs vises.
3. Donnees disponibles et choix de travailler sur des reviews en anglais.
4. Architecture applicative et separation des couches.
5. Integration des modeles reels.
6. Evaluation offline et lecture des metriques.
7. Monitoring, securite et exploitabilite.
8. CI/CD, containerisation et reproductibilite.
9. Limites actuelles.
10. Roadmap MLOps apres la soutenance.

## Demo recommandee en direct

1. Montrer l'interface Streamlit.
2. Analyser une review negative sur le SAV.
3. Analyser une review positive sur livraison + produit.
4. Montrer le flag `human review` sur un cas ambigu.
5. Ouvrir `/health` puis `/metrics`.
6. Montrer `reports/default_evaluation.md`.

## Messages cle a verbaliser

- Le projet n'est pas seulement un modele NLP: c'est une base MLOps exploitable.
- Les livrables sont alignes avec les 4 phases du kickoff Liora.
- La detection des themes est solide sur le dataset de demonstration.
- Le sentiment reste perfectible, ce qui justifie la phase suivante de calibration et retraining.
- Les limites sont tracees, mesurees et documentees.

## Questions probables du jury

### Pourquoi un POC "production-shaped" et pas une simple demo notebook ?

Parce que le kickoff demande une logique MLOps: API, packaging, testabilite, deployabilite et monitoring.

### Pourquoi les commentaires sont en anglais alors que la documentation est en francais ?

Parce que les modeles et les donnees du projet actuel sont calibres pour l'anglais, tandis que le projet academique et sa gouvernance sont portes en francais.

### Quelle est la prochaine priorite technique ?

Industrialiser la pipeline d'entrainement, figer le mapping de classes de sentiment et evaluer sur un vrai dataset de validation projet.

## Checklist avant passage

- `pytest -q`
- `py -3 pipelines/evaluate_default.py`
- `streamlit run app.py`
- `uvicorn api_app:app --host 0.0.0.0 --port 8000`
- verifier le backend actif dans `/health`
