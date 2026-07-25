# Dossier de validation finale — Review Insights+

Date de validation : 25 juillet 2026  
Branche validée : `main`  
Révision de départ : `bf08c7d`

## Verdict

La plateforme complète est opérationnelle. Les tests automatisés passent, les dix-sept services du profil `control` démarrent, les API et interfaces répondent, deux jeux de données distincts ont servi à entraîner plusieurs versions du modèle, MLflow conserve les métriques et artefacts, Dagster exécute les pipelines de réentraînement et de détection de dérive, et la chaîne Prometheus–Alertmanager reçoit les alertes.

## Résultats vérifiés

- Qualité du code : `ruff check .` réussi.
- Tests : **113 réussis, 0 échec, 0 ignoré**.
- Couverture : **71,15 %** (`2 511 / 3 529` lignes).
- Docker Compose : configuration valide et **17 services** démarrés.
- Smoke test fonctionnel : **10 contrôles sur 10** réussis.
- Cibles Prometheus : **13 sur 13** disponibles.
- Registry MLflow : modèle `review-insights-project-models`, versions **1, 2 et 3** en état `READY`.
- Jeux d’entraînement :
  - `soutenance_reference_40_v1` — 40 avis, exécution MLflow `736ea3f065ed486385e98d86f1b70ccf`, version 1, alias `baseline`;
  - `soutenance_retraining_120_v2` — 120 avis équilibrés, exécution MLflow `7d80bfd9812a4b1e8ff95bb8da62abcc`, version 2;
  - le même jeu de 120 avis a ensuite été traité par le job Dagster réel, produisant la version 3 et l’alias `candidate`.
- Réentraînement Dagster : exécution `c9f57164-b39b-4939-945b-f9cfe02fdc70`, état `RUN_SUCCESS`.
- Monitoring de dérive Dagster : exécution `64228eb5-c9bc-466b-9c0f-ecf311137dd1`, état `RUN_SUCCESS`.
- Dérive détectée sur 33 prédictions et 11 retours humains :
  - exactitude combinée feedback : `0,090909`;
  - divergence JS sentiment : `0,251484`;
  - divergence JS thèmes : `0,102465`;
  - recommandation : `retraining_recommended`;
  - réentraînement automatique autorisé : `true`.
- Alertes actives :
  - `ReviewInsightsDriftDetected` — `firing`;
  - `ReviewInsightsPerformanceDrift` — `firing`.

## Matrice des services et preuves

| Service Compose | État vérifié | Preuve visuelle principale |
|---|---:|---|
| `streamlit` | démarré | [01 — application opérationnelle](captures/01_streamlit_analyse.png) |
| `api` | sain | [02 — API d’inférence](captures/02_api_inference_swagger.png) |
| `data` | sain | [03 — API de données](captures/03_api_data_swagger.png) |
| `monitoring` | sain | [04 — API de monitoring](captures/04_api_monitoring_swagger.png) |
| `mlflow` | sain | [05 — versions et alias](captures/05_mlflow_registre_versions.png) |
| `dagster-webserver` | sain | [06 — orchestration](captures/06_dagster_orchestration.png) |
| `dagster-code` | sain | [11 — pipeline d’entraînement réussi](captures/11_dagster_training_reussi.png) |
| `dagster-daemon` | démarré | [12 — pipeline de dérive réussi](captures/12_dagster_drift_reussi.png) |
| `dagster-postgres` | sain | [07 — cibles de supervision](captures/07_prometheus_cibles.png) |
| `postgres` | sain | [05 — persistance MLflow](captures/05_mlflow_registre_versions.png) |
| `minio` | sain | [10 — buckets et artefacts](captures/10_minio_bucket_artifacts.png) |
| `minio-init` | terminé avec code 0 | [10 — buckets initialisés](captures/10_minio_bucket_artifacts.png) |
| `prometheus` | démarré | [13 — alertes en firing](captures/13_prometheus_alertes_drift_firing.png) |
| `alertmanager` | démarré | [09 — alertes reçues](captures/09_alertmanager_drift_firing.png) |
| `pushgateway` | démarré | [08 — métriques de pipeline](captures/08_pushgateway_metriques.png) |
| `cadvisor` | sain | [07 — cible cAdvisor disponible](captures/07_prometheus_cibles.png) |
| `blackbox-exporter` | démarré | [07 — sondes disponibles](captures/07_prometheus_cibles.png) |
| `grafana` | démarré | [14](captures/14_grafana_api_inference.png), [15](captures/15_grafana_donnees_modeles.png), [16](captures/16_grafana_systeme_orchestration.png), [17](captures/17_grafana_qualite_metier.png) |

`minio-init` est volontairement un conteneur ponctuel : sa sortie normale avec code `0` confirme l’initialisation des buckets.

## Parcours fonctionnels couverts

Le smoke test a validé le backend actif, une analyse unitaire, un lot de 12 avis, l’évaluation de référence, la boucle de correction humaine, l’exposition des métriques, le frontend, ainsi que les pipelines locaux d’annotation et de publication.

Les tests automatisés couvrent également les cinq espaces Streamlit (`Analyse`, `Analyse groupée`, `Données`, `Suivi`, `Évaluation`), les états d’erreur, les contrats frontend, les contrôles qualité des données, le routage humain, l’export et les composants d’orchestration.

## Galerie de soutenance

### Produit et API

- [Application Streamlit](captures/01_streamlit_analyse.png)
- [API d’inférence](captures/02_api_inference_swagger.png)
- [API de données](captures/03_api_data_swagger.png)
- [API de monitoring](captures/04_api_monitoring_swagger.png)

### MLOps et modèles

- [Registry MLflow — modèles](captures/05_mlflow_registre_modeles.png)
- [Registry MLflow — versions, alias et métriques](captures/05_mlflow_registre_versions.png)
- [Dagster — orchestration](captures/06_dagster_orchestration.png)
- [Dagster — entraînement réussi](captures/11_dagster_training_reussi.png)
- [Dagster — dérive réussie](captures/12_dagster_drift_reussi.png)
- [MinIO — stockage des artefacts](captures/10_minio_bucket_artifacts.png)

### Observabilité

- [Prometheus — 13 cibles disponibles](captures/07_prometheus_cibles.png)
- [Pushgateway — métriques de pipeline](captures/08_pushgateway_metriques.png)
- [Prometheus — alertes de dérive actives](captures/13_prometheus_alertes_drift_firing.png)
- [Alertmanager — alertes reçues](captures/09_alertmanager_drift_firing.png)
- [Grafana — API et inférence](captures/14_grafana_api_inference.png)
- [Grafana — données et modèles](captures/15_grafana_donnees_modeles.png)
- [Grafana — système et orchestration](captures/16_grafana_systeme_orchestration.png)
- [Grafana — qualité métier](captures/17_grafana_qualite_metier.png)

## Reproductibilité

```powershell
docker compose --profile control up -d --build
ruff check .
pytest
docker exec reviewinsightspoc-dagster-code-1 dagster job execute `
  -m orchestration.definitions `
  -j model_training_job `
  -c orchestration/run_configs/model_training_test.yaml
docker exec reviewinsightspoc-dagster-code-1 dagster job execute `
  -m orchestration.definitions `
  -j drift_monitoring_job
```

Les identifiants d’exécution, métriques et états structurés sont conservés dans [synthese_validation.json](synthese_validation.json). Le détail de couverture est conservé dans `../final_validation/coverage_current.json`.

