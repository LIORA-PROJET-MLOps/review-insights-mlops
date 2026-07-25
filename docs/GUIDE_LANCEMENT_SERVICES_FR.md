# Guide simple de lancement des services

Ce guide explique comment lancer Review Insights+ depuis Windows PowerShell, service par service.
Les commandes sont prevues pour etre copiees-collees depuis la racine du projet.

## 0. Prerequis

Avant de commencer :

- Docker Desktop doit etre lance ;
- PowerShell doit etre ouvert ;
- le terminal doit etre place dans le dossier du projet.

```powershell
cd "<chemin-vers-le-dossier-du-projet>"
docker version
docker compose version
```

Si Docker ne repond pas, ouvrir Docker Desktop et attendre que le moteur Docker soit pret.

## 1. Verification rapide de la configuration

Cette commande verifie que `compose.yaml` est lisible par Docker Compose.

```powershell
docker compose config --quiet
```

Si la commande ne retourne rien, c'est bon.

## 2. Optionnel : arreter une ancienne execution

Cette commande arrete les conteneurs du projet sans supprimer les donnees persistantes.

```powershell
docker compose --profile control down --remove-orphans
```

Ne pas utiliser `-v` sauf si tu veux supprimer les donnees Docker du projet
MLflow, MinIO, Grafana, Prometheus, Dagster et feedbacks.

## 3. Lancement complet en une seule commande

Si tu veux tout lancer directement, c'est la commande la plus simple.

```powershell
docker compose --profile control up --build -d
```

Ensuite, attendre quelques minutes au premier demarrage. L'API peut prendre du temps pendant le
chargement initial du backend de prediction.

## 4. Lancement service par service

Si tu veux comprendre et controler le demarrage, lance les services dans cet ordre.

### 4.1 PostgreSQL pour MLflow

Stocke les metadonnees MLflow : runs, experiences, model registry.

```powershell
docker compose up -d postgres
docker compose ps postgres
```

### 4.2 MinIO

Stocke les artefacts MLflow et les objets du projet.

```powershell
docker compose up -d minio
docker compose ps minio
```

### 4.3 Initialisation des buckets MinIO

Cree les buckets necessaires a MLflow et aux donnees.

```powershell
docker compose up minio-init
```

Le conteneur `minio-init` peut terminer en statut `Exited (0)` : c'est normal.

### 4.4 MLflow

Interface de tracking des experiences, artefacts et versions candidates de modele.

```powershell
docker compose up -d --build mlflow
docker compose ps mlflow
```

Test :

```powershell
Invoke-RestMethod http://localhost:5000/health
```

### 4.5 API d'inference

Service FastAPI qui analyse les reviews.

```powershell
docker compose up -d --build api
docker compose ps api
```

Test :

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### 4.6 Service data

Expose les datasets, evaluations, feedbacks humains et rapports de drift.

```powershell
docker compose up -d --build data
docker compose ps data
```

Test :

```powershell
Invoke-RestMethod http://localhost:8001/health
```

### 4.7 Service monitoring

Expose les metriques applicatives en JSON et au format Prometheus.

```powershell
docker compose up -d --build monitoring
docker compose ps monitoring
```

Test :

```powershell
Invoke-RestMethod http://localhost:9000/health
```

### 4.8 Interface Streamlit

Interface metier pour analyser les avis, consulter le monitoring et enregistrer du feedback.

```powershell
docker compose up -d --build streamlit
docker compose ps streamlit
```

Test :

```powershell
(Invoke-WebRequest http://localhost:8501 -UseBasicParsing).StatusCode
```

### 4.9 PostgreSQL Dagster

Base de donnees interne de Dagster pour les runs, schedules et capteurs.

```powershell
docker compose --profile control up -d dagster-postgres
docker compose --profile control ps dagster-postgres
```

### 4.10 Dagster code server

Charge les definitions Dagster du projet : jobs, assets, schedules et sensors.

```powershell
docker compose --profile control up -d --build dagster-code
docker compose --profile control ps dagster-code
```

Test des definitions :

```powershell
docker compose exec -T dagster-code dagster definitions validate -m orchestration.definitions
```

### 4.11 Dagster webserver et daemon

Le webserver expose l'interface Dagster. Le daemon execute les schedules et sensors.

```powershell
docker compose --profile control up -d --build dagster-webserver dagster-daemon
docker compose --profile control ps dagster-webserver dagster-daemon
```

Test :

```powershell
Invoke-RestMethod http://localhost:3001/server_info
```

### 4.12 Services de supervision systeme

Ces services alimentent Prometheus.

```powershell
docker compose --profile control up -d pushgateway alertmanager blackbox-exporter cadvisor
docker compose --profile control ps pushgateway alertmanager blackbox-exporter cadvisor
```

### 4.13 Prometheus

Collecte les metriques API, monitoring, Dagster batch, disponibilite et systeme.

```powershell
docker compose --profile control up -d --build prometheus
docker compose --profile control ps prometheus
```

Test :

```powershell
Invoke-RestMethod http://localhost:9090/-/ready
```

### 4.14 Grafana

Affiche les dashboards API, donnees/modeles, systeme/orchestration et qualite metier.

```powershell
docker compose --profile control up -d grafana
docker compose --profile control ps grafana
```

Test :

```powershell
Invoke-RestMethod http://localhost:3000/api/health
```

## 5. Verifier que tout est lance

```powershell
docker compose --profile control ps
```

Les services principaux doivent etre en `running` ou `healthy`.

Healthchecks utiles :

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:9000/health
Invoke-RestMethod http://localhost:5000/health
Invoke-RestMethod http://localhost:3001/server_info
Invoke-RestMethod http://localhost:9090/-/ready
Invoke-RestMethod http://localhost:9093/-/ready
Invoke-RestMethod http://localhost:3000/api/health
(Invoke-WebRequest http://localhost:8501 -UseBasicParsing).StatusCode
```

## 6. URLs a ouvrir dans le navigateur

| Service | URL | Role |
| --- | --- | --- |
| Streamlit | http://localhost:8501 | Interface metier principale |
| API FastAPI | http://localhost:8000/docs | Documentation API |
| Data service | http://localhost:8001/docs | Datasets, evaluation, feedback, drift |
| Monitoring service | http://localhost:9000/docs | Health et metriques applicatives |
| MLflow | http://localhost:5000 | Tracking, runs et model registry |
| Dagster | http://localhost:3001 | Pipelines, jobs, schedules, sensors |
| Prometheus | http://localhost:9090 | Metriques et alertes |
| Alertmanager | http://localhost:9093 | Alertes recues |
| Grafana | http://localhost:3000 | Dashboards |
| MinIO console | http://localhost:9101 | Stockage objet local |

Identifiants locaux par defaut :

- Grafana : `admin` / `change-me-grafana`
- MinIO : `review-insights` / `change-me-minio-secret`

Ces mots de passe sont des valeurs de developpement local. Les changer pour un environnement partage.

## 7. Lancer un test fonctionnel rapide

Quand les services API, data, monitoring et Streamlit sont demarres :

```powershell
.\scripts\run_functional_smoke_tests.ps1
```

Ce test verifie notamment :

- les healthchecks ;
- une analyse unitaire ;
- un batch CSV ;
- le service data ;
- la boucle feedback humain ;
- les metriques API et Prometheus ;
- l'interface Streamlit.

## 8. Tester Dagster avec un CSV

Mettre un CSV dans le dossier surveille par Dagster :

```powershell
Copy-Item "C:\chemin\vers\mon_dataset.csv" "data\raw\incoming\mon_dataset.csv"
```

Exemple avec un CSV de test place sur le Bureau :

```powershell
Copy-Item "<chemin-vers-votre-csv>\reviews_dagster_test_120.csv" "data\raw\incoming\reviews_dagster_test_120.csv"
```

Puis ouvrir Dagster :

```powershell
Start-Process "http://localhost:3001"
```

Dans Dagster :

1. ouvrir `Jobs` ;
2. choisir `model_training_job` pour lancer le pipeline complet ;
3. ouvrir `Launchpad` ;
4. configurer `source_csv` si necessaire ;
5. cliquer sur `Launch Run`.

Les automatisations disponibles :

- `daily_full_pipeline_schedule` : tous les jours a 19:00 Europe/Paris ;
- `hourly_drift_monitoring_schedule` : toutes les heures a la minute 15 ;
- `incoming_review_csv_sensor` : surveille les nouveaux CSV ;
- `drift_retraining_sensor` : lance un retraining seulement si drift + nouveau CSV etiquete pret.

## 9. Lire les logs

Logs API :

```powershell
docker compose logs -f api
```

Logs Streamlit :

```powershell
docker compose logs -f streamlit
```

Logs Dagster :

```powershell
docker compose --profile control logs -f dagster-webserver dagster-daemon dagster-code
```

Logs Prometheus/Grafana :

```powershell
docker compose --profile control logs -f prometheus grafana
```

## 10. Si tu es sur un autre ordinateur en remote

Depuis une autre machine, remplacer `localhost` par l'adresse IP de la machine qui lance Docker.

Exemple :

```powershell
Test-NetConnection 192.168.1.50 -Port 8501
Test-NetConnection 192.168.1.50 -Port 3001
Test-NetConnection 192.168.1.50 -Port 3000
```

Puis ouvrir :

- `http://192.168.1.50:8501` pour Streamlit ;
- `http://192.168.1.50:3001` pour Dagster ;
- `http://192.168.1.50:3000` pour Grafana.

Si le test de port echoue, verifier :

- que Docker tourne sur la machine distante ;
- que le service est bien `running` avec `docker compose --profile control ps` ;
- que le firewall Windows autorise le port ;
- que tu utilises l'IP de la machine Docker, pas l'IP de ton poste client.

## 11. Ports principaux

| Port | Service |
| --- | --- |
| 8000 | API inference |
| 8001 | Data service |
| 9000 | Monitoring gateway |
| 8501 | Streamlit |
| 5000 | MLflow |
| 3001 | Dagster |
| 9090 | Prometheus |
| 9091 | Pushgateway |
| 9093 | Alertmanager |
| 3000 | Grafana |
| 9100 | MinIO API |
| 9101 | MinIO console |

## 12. Commandes utiles de depannage

Voir tous les conteneurs :

```powershell
docker compose --profile control ps
```

Redemarrer un service :

```powershell
docker compose restart api
```

Reconstruire un service :

```powershell
docker compose build api
docker compose up -d api
```

Voir les derniers logs d'un service :

```powershell
docker compose logs --tail=100 api
```

Arreter tout le projet sans supprimer les donnees :

```powershell
docker compose --profile control down
```

Reset complet avec suppression des volumes Docker du projet :

```powershell
docker compose --profile control down -v
```

Attention : le reset complet supprime les donnees locales de MLflow, MinIO, Dagster, Grafana,
Prometheus, feedbacks et predictions persistantes.
