# Contenu propose pour les slides de soutenance

Format conseille: 12 slides, 12 a 15 minutes, puis demonstration.

## Slide 1 - Review Insights+

Message: transformer les avis clients en insights actionnables avec une chaine MLOps gouvernee.

- analyse sentiment et themes;
- revue humaine des cas ambigus;
- monitoring de performance et retraining controle.

Visuel: `site/assets/product-overview.svg`.

## Slide 2 - Probleme et valeur metier

Message: prioriser rapidement livraison, SAV et produit sans perdre le controle humain.

- traitement unitaire et batch;
- synthese, confiance, evidences et action recommandee;
- feedback humain reutilisable pour mesurer la qualite.

Visuel: capture Streamlit `01_streamlit_analyse.png`.

## Slide 3 - Architecture de bout en bout

Message: l'application est un produit multi-services, pas un notebook.

- FastAPI, Streamlit et service data;
- Dagster pour l'orchestration;
- MLflow, PostgreSQL et MinIO pour la gouvernance ML;
- Prometheus, Alertmanager et Grafana pour l'exploitation.

Visuel: `site/assets/architecture-stack.svg`.

## Slide 4 - Gouvernance des donnees

Message: aucune donnee n'entre dans le training sans contrat et quality gates.

- validation, deduplication et quarantaine;
- splits deterministes et checksums;
- manifest lie au commit source;
- test final: 120/120 valides, 0 rejetee.

Visuel: capture Grafana `12_grafana_data_models_drift.png`.

## Slide 5 - Training et Model Registry

Message: un modele est trace, evalue et enregistre comme candidat avant toute promotion.

- run Dagster reussi;
- artefacts et metriques dans MLflow;
- candidat v2 `READY`;
- promotion testee en dry-run.

Visuels: `05_dagster_training_logs_success.png` et
`08_mlflow_model_registry_candidate.png`.

## Slide 6 - Qualite modele, lecture honnete

Message: distinguer preuve technique et performance reelle.

- reference active: accuracy sentiment 0,575;
- F1 themes 0,8877;
- le score 1,0 du candidat vient du petit dataset synthetique;
- la performance sentiment doit encore progresser avant production.

## Slide 7 - Inference et experience utilisateur

Message: le backend `project_models_v1` sert les analyses avec une API observable.

- 30 avis traites dans le scenario de controle;
- erreur HTTP 0 %;
- revue humaine 40 %;
- contradictions 20 % dans le test volontaire.

Visuel: capture Grafana `11_grafana_api_inference.png`.

## Slide 8 - Boucle feedback et drift

Message: les commentaires non etiquetes sont analyses; seul le feedback etiquete peut alimenter un
retraining controle.

- drift horaire a la minute 15;
- 30 predictions et 10 feedbacks joints;
- accuracy feedback 0,10 dans le scenario degrade;
- recommandation de retraining declenchee.

Visuels: `04_streamlit_retraining_feedback.png` et
`06_dagster_drift_run_success.png`.

## Slide 9 - Garde-fous de retraining

Message: un drift ne remplace jamais automatiquement le champion.

- sensor actif;
- nouveau CSV etiquete obligatoire;
- prevention des datasets deja ingeres;
- quality gates et promotion separee.

Visuel: capture Dagster `07_dagster_automation_schedules_sensors.png`.

## Slide 10 - Observabilite operationnelle

Message: l'etat technique et metier est visible sur une seule stack.

- 17 services actifs;
- 13/13 targets Prometheus UP;
- alertes de drift effectivement declenchees;
- dashboards API, data/modeles, systeme et metier.

Visuels: `09_prometheus_targets_all_up.png`, `10_prometheus_alerts_drift.png` et
`13_grafana_system_orchestration.png`.

## Slide 11 - Preuves de qualite logicielle

Message: le fonctionnement est soutenu par des controles reproductibles.

- 106 tests passes, 4 skips conditionnels hote;
- couverture 78,32 % pour un seuil de 70 %;
- Ruff propre;
- smoke fonctionnel 10/10;
- runs training, drift et promotion reussis.

## Slide 12 - Verdict et prochaines etapes

Message: POC/MVP complet et demonstrable, avec une trajectoire de production claire.

- aujourd'hui: chaine bout en bout operationnelle et gouvernee;
- demain: donnees reelles, performance sentiment, secrets et receiver d'alerte;
- ensuite: retention, sauvegardes, haute disponibilite et charge.

Conclusion orale proposee: « Le projet ne se contente pas de predire: il sait expliquer son etat,
detecter une degradation et recommander un retraining sans perdre le controle humain. »

## Scenario de demonstration en 4 minutes

1. Charger/analyser un avis dans Streamlit.
2. Montrer le run training `SUCCESS` et le candidat MLflow.
3. Montrer le drift detecte, les deux alertes et la recommandation.
4. Terminer sur Grafana avec les vues metier et systeme.

Toutes les captures sont disponibles dans `reports/final_validation/screenshots/`.
