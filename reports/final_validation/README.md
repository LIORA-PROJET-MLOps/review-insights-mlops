# Dossier de preuves de validation finale

Validation executee le 1er juillet 2026 sur la stack Docker Compose locale complete.

## Resultats machine-readables

- `validation_summary.json`: verdict et metriques principales.
- `coverage.json`: rapport de couverture pytest.
- `screenshots/`: captures des interfaces, logs, metriques et dashboards.

## Index des captures

| # | Preuve | Fichier |
| --- | --- | --- |
| 01 | Analyse Streamlit | `screenshots/01_streamlit_analyse.png` |
| 02 | Vue monitoring Streamlit | `screenshots/02_streamlit_monitoring_drift.png` |
| 03 | Metriques drift/feedback Streamlit | `screenshots/03_streamlit_drift_feedback.png` |
| 04 | Recommandation de retraining | `screenshots/04_streamlit_retraining_feedback.png` |
| 05 | Logs Dagster du training reussi | `screenshots/05_dagster_training_logs_success.png` |
| 06 | Run Dagster drift reussi | `screenshots/06_dagster_drift_run_success.png` |
| 07 | Schedules et sensors Dagster | `screenshots/07_dagster_automation_schedules_sensors.png` |
| 08 | MLflow Model Registry, candidat v2 | `screenshots/08_mlflow_model_registry_candidate.png` |
| 09 | Cibles Prometheus disponibles | `screenshots/09_prometheus_targets_all_up.png` |
| 10 | Alertes drift Prometheus | `screenshots/10_prometheus_alerts_drift.png` |
| 11 | Grafana API et inference | `screenshots/11_grafana_api_inference.png` |
| 12 | Grafana donnees, modeles et drift | `screenshots/12_grafana_data_models_drift.png` |
| 13 | Grafana systeme et orchestration | `screenshots/13_grafana_system_orchestration.png` |
| 14 | Grafana qualite metier | `screenshots/14_grafana_business_quality.png` |

Les alertes de drift visibles sont attendues: elles proviennent d'un jeu de feedback volontairement
incorrect destine a prouver le declenchement de la detection, de l'alerte et de la recommandation de
retraining.
