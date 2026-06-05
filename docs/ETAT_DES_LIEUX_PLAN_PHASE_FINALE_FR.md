# Etat des lieux et plan de phase finale

Date de l'audit: 3 juin 2026

## Mise a jour apres corrections

Les constats et blocages de ce document decrivent l'etat initial observe pendant l'audit. La phase
de correction a ensuite ete executee le 3 juin 2026.

Statut actuel:

- les blocages P0 identifies ont ete corriges;
- l'evaluation preserve maintenant la verite terrain et utilise un dataset de reference distinct de
  40 avis;
- l'ingestion applique un contrat data versionne, une validation stricte, une quarantaine, des hash
  SHA-256 et des splits deterministes;
- le manifest modele contient les hash des artefacts et la revision Hugging Face est immuable;
- Streamlit consomme les services API, data et monitoring au lieu de charger ses propres modeles;
- les bundles Hugging Face, les images Docker, Docker Compose, MLflow, les API et le frontend ont ete
  testes de bout en bout;
- la suite locale compte **47 tests passes** avec **73 % de couverture**.
- mise a jour du 5 juin 2026: la suite locale compte maintenant **69 tests passes** avec environ
  **78 % de couverture**; l'evaluation expose aussi F1 macro sentiment, F1 macro themes, details
  par classe, matrice de confusion, taux de revue humaine; le healthcheck expose un profil securite;
  le monitoring suit `X-Request-ID`, metriques HTTP, taux d'erreur et export Prometheus enrichi;
  les gates de promotion acceptent des seuils minimums et des plafonds de metriques.

Le projet est maintenant une base de POC MLOps solide et reproductible pour une demonstration
controlee. Il ne doit pas encore etre presente comme une plateforme de production: les priorites P1
restantes sont notamment un dataset metier plus large avec labels de sentiment par theme, un stockage
durable des donnees et artefacts, un backend MLflow industrialise, un workflow de promotion et
rollback, ainsi que des dashboards et alertes persistants.

## Verdict executif

Le projet est une bonne base de POC MLOps demonstrable: le code est modulaire, les services sont separes dans Docker Compose, les modeles reels sont charges avec un fallback, les tests locaux passent, la CI est active, et les integrations GitHub Pages, Hugging Face et MLflow sont preparees.

> Note: le verdict et les sections suivantes constituent le diagnostic initial avant corrections.

Le projet n'est pas encore pret pour etre presente comme un MVP fiable en environnement partage ou comme une base de production. Le principal blocage n'est pas l'absence de fonctionnalites, mais la fiabilite des preuves:

- les metriques de themes publiees a `1.0` sont invalides, car les predictions ecrasent les colonnes de verite terrain avant le calcul;
- l'entrainement et l'evaluation utilisent le meme dataset;
- les modeles de sentiment par theme sont entraines avec un label de sentiment global;
- plusieurs integrations annoncees ne sont pas reproductibles de bout en bout;
- la gouvernance des donnees reste locale et minimale.

Position recommandee:

- **Pret pour une demonstration controlee**, apres correction des blocages P0.
- **Pas pret pour un MVP partage**, tant que les contrats data, les gates de qualite, la securite des services et la promotion modele ne sont pas en place.
- **Pas pret pour la production**, tant que la persistance, l'observabilite, la gestion des secrets, le stockage des artefacts et les operations ne sont pas industrialises.

## Perimetre audite

L'audit couvre:

- architecture Python dans `src/review_insights/`;
- API d'inference, service data, monitoring et frontend Streamlit;
- pipelines d'ingestion, entrainement, evaluation et tracking MLflow;
- artefacts modeles et manifest;
- Dockerfiles, Docker Compose et bundles Hugging Face;
- CI GitHub Actions, GitHub Pages et frontend statique;
- structure locale des donnees et pratiques de gouvernance.

## Verifications realisees

- `pytest -q`: **33 tests passes** localement.
- `docker compose config --quiet`: configuration Compose valide.
- Docker Compose runtime non verifie: Docker Desktop n'etait pas demarre pendant l'audit.
- CI GitHub Actions du commit `81b3c54`: **success** le 2 juin 2026.
- Deploiement GitHub Pages du commit `81b3c54`: **success** le 2 juin 2026.
- GitHub Pages accessible: `https://liora-projet-mlops.github.io/review-insights-mlops/`.
- Repo modele Hugging Face accessible avec les 6 fichiers attendus au commit:
  `1d6a5bd3e653ba75b6c8fed614e156d1a3c73779`.
- API Hugging Face accessible apres warm-up sur `/health`, `/openapi.json` et `/v1/evaluate/default`.
- Le premier appel `/health` a expire et un appel `/docs` a retourne `500`, ce qui montre un risque de cold start ou de disponibilite variable.
- Le bundle API Hugging Face genere par `scripts/build_hf_space_bundle.ps1` ne peut pas etre importe, car `security.py` n'est pas copie.

## Architecture actuelle

```text
Frontend Streamlit ---------------------> Service Python local + modeles locaux

Frontend statique GitHub Pages / HF ----> API FastAPI Hugging Face

Docker Compose:
  streamlit
  api ----------------------------------> modeles montes depuis ./models
  data ---------------------------------> evaluation par defaut + MLflow
  monitoring ---------------------------> API /metrics
  mlflow -------------------------------> SQLite + artefacts sur volume local

Pipelines CLI:
  CSV -> raw/archive -> processed -> validated -> entrainement -> artefacts -> MLflow candidate
```

La cible annoncee est microservices, mais le frontend Streamlit utilise encore directement
`ReviewAnalysisService` et ses propres modeles. Les variables `API_URL`, `DATA_URL` et
`MONITORING_URL` du service Streamlit ne sont pas consommees par l'application.

## Niveau de maturite par domaine

| Domaine | Etat | Commentaire |
| --- | --- | --- |
| Structure du code | Bon | Separation claire entre schemas, service, backend modele, evaluation et monitoring. |
| API d'inference | Partiel | Contrat Pydantic, healthcheck et securite POC presents, mais pas de SLO, logs structures ou batch API. |
| Donnees | Bloquant pour MVP | Ingestion CSV locale utile, mais pas de contrat versionne, hash, quarantaine, lineage complet, PII ou stockage durable. |
| Evaluation modele | Bloquant | Metriques de themes faussees et absence de split train/validation/test. |
| Training | Partiel | Pipeline reproductible en forme, mais semantique des labels et evaluation a revoir. |
| MLflow | Partiel | Tracking et enregistrement candidat presents; backend SQLite et promotion non industrialises. |
| Monitoring | Partiel | Export Prometheus existe, mais les compteurs sont en memoire et incomplets. |
| Deploiement Docker | Partiel | Compose valide, mais runtime non verifie pendant l'audit et CI ne construit pas tous les services. |
| Hugging Face | Bloquant pour redeploiement | Deploiement actuel accessible, mais bundle local casse et revision modele mutable. |
| CI/CD | Partiel | Tests et build racine presents, mais pas de lint, type check, couverture, securite, contrats ou smoke tests de services. |
| Securite | POC uniquement | Cle API et rate limit en memoire; services internes, MLflow, CORS et secrets a durcir. |
| Documentation | Bonne mais en derive | Documentation riche, avec plusieurs ecarts par rapport au code actuel. |

## Points forts a conserver

- Architecture applicative lisible et suffisamment modulaire.
- API FastAPI avec schemas explicites et healthcheck.
- Backend modele reel avec fallback heuristique.
- Artefacts modeles regroupes et manifest presents.
- Pipelines CLI faciles a lancer depuis le depot.
- Tests unitaires couvrant API, securite POC, data store, training et MLflow.
- Images Docker executees avec un utilisateur non-root pour les services locaux.
- Tracking MLflow et Model Registry deja amorces.
- Export de metriques au format Prometheus via le service monitoring.
- GitHub Actions et GitHub Pages fonctionnels sur le dernier commit.

## Blocages critiques P0

### 1. Les metriques de themes sont invalides

Dans `src/review_insights/service.py`, `merged.update(result)` remplace les colonnes
`theme_livraison`, `theme_sav` et `theme_produit` de la verite terrain par les predictions.
Dans `src/review_insights/evaluation.py`, les colonnes dites de verite et de prediction deviennent
donc identiques.

Consequence:

- `theme_exact_match`, `theme_precision_macro` et `theme_recall_macro` peuvent etre artificiellement
  egales a `1.0`;
- les rapports dans `reports/` et les runs MLflow ne sont pas utilisables comme preuve de qualite;
- une promotion automatique basee sur ces metriques serait dangereuse.

Recalcul independant realise pendant l'audit avec les modeles actifs:

| Dataset | Lignes | Sentiment accuracy | Theme exact match | Theme precision macro | Theme recall macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dataset par defaut | 8 | 0.7500 | 0.6250 | 0.8333 | 0.8667 |
| `data/sample/reviews_poc_test.csv` | 40 | 0.5750 | 0.6750 | 0.8787 | 0.8972 |

Ces chiffres sont seulement un diagnostic. Ils ne constituent pas encore une evaluation finale,
car l'independance entre donnees d'entrainement et donnees de test n'est pas garantie.

### 2. Fuite entre entrainement et evaluation

`pipelines/train_models.py` evalue les artefacts sur le meme DataFrame que celui utilise pour
l'entrainement. Il n'existe pas de split train, validation et test, ni de seed explicite, ni de
dataset de test gele.

Consequence:

- les scores de training sont optimistes;
- aucun gate de promotion modele ne peut etre considere fiable;
- les regressions sont difficiles a detecter.

### 3. Semantique des modeles de sentiment par theme

Les trois modeles `sent_livraison`, `sent_sav` et `sent_produit` sont entraines avec la meme cible
`sentiment_label`, qui est un sentiment global. L'API presente ensuite ces sorties comme des
sentiments par theme.

Il faut choisir une cible claire:

- soit ajouter des labels `sentiment_livraison`, `sentiment_sav`, `sentiment_produit`;
- soit ne plus presenter les sorties comme des sentiments par theme;
- soit entrainer un modele multi-tache avec une taxonomie de labels explicite.

### 4. Redeploiement Hugging Face non reproductible

Deux problemes sont presents:

- `ARTIFACT_FILENAMES` ne contient pas `manifest.json`, donc un chargement propre depuis Hugging
  Face ne recupere pas le mapping de classes versionne;
- `scripts/build_hf_space_bundle.ps1` ne copie pas `src/review_insights/security.py`, alors que
  `api.py` l'importe.

Le bundle genere pendant l'audit echoue avec:

```text
ModuleNotFoundError: No module named 'src.review_insights.security'
```

Le Space online peut fonctionner grace a un deploiement anterieur ou a un cache persistant, mais
le depot actuel ne permet pas de le reconstruire proprement.

### 5. Integration frontend incoherente

- Streamlit charge directement les modeles et maintient ses propres metriques.
- Les variables Compose `API_URL`, `DATA_URL` et `MONITORING_URL` ne sont pas utilisees.
- Le frontend statique lit `payload.sentiment_accuracy`, alors que l'API retourne
  `payload.summary.sentiment_accuracy`.
- La saisie d'une cle API dans un frontend public expose le secret au navigateur.

La phase finale doit avoir une seule source de verite pour l'inference: l'API.

## Ecarts importants P1

### Gouvernance des donnees

La structure `raw / processed / validated / registry` est une bonne base, mais elle ne couvre pas
encore les exigences d'un pipeline solide:

- pas de schema de donnees versionne;
- pas de validation explicite des colonnes obligatoires avant nettoyage;
- pas de fichier de quarantaine avec raison de rejet;
- les doublons sont supprimes sans etre comptes dans `rows_rejected`;
- pas de checksum du fichier source ou des datasets produits;
- pas de lineage entre source, dataset, run MLflow et modele;
- pas de metadata sur la source, la licence, la langue, le consentement, la PII ou la retention;
- registre JSON non atomique et non adapte a des executions concurrentes;
- pas de stockage durable hors du poste local;
- pas de split stable et versionne;
- pas de controle de distribution ou de drift.

### Artefacts et supply chain modele

- Les fichiers `joblib` peuvent executer du code lors du chargement. Ils doivent venir d'une source
  de confiance, etre hashes et charges depuis une revision immuable.
- `HF_MODEL_REVISION=main` est mutable. Une revision de commit ou un tag immuable doit etre utilise.
- Le manifest ne contient pas les checksums, versions exactes de bibliotheques, commit Git, dataset
  version, schema version ou metriques de validation.
- Les modeles sont stockes a la fois dans Git et Hugging Face, sans source de verite explicite.

### Securite et exploitation

- `ALLOWED_ORIGINS=*`, `TRUSTED_HOSTS=*` et `ENABLE_DOCS=true` sont adaptes au local, pas a un
  environnement partage.
- La cle API et le rate limit en memoire ne conviennent pas a plusieurs replicas.
- Le service `data`, le service `monitoring` et MLflow sont exposes sur des ports hote sans
  authentification.
- Le backend MLflow SQLite et les artefacts sur volume local ne conviennent pas a un service durable.
- Les logs ne sont pas structures et il n'existe pas de correlation ID.
- Il n'existe pas de runbook de rollback ou de sauvegarde.

### Observabilite

Le service monitoring exporte deja un format Prometheus, contrairement a certaines sections de la
documentation. Il manque encore:

- latence par endpoint et percentiles;
- taux d'erreur HTTP;
- taille des payloads;
- temps de chargement modele;
- version exacte du modele dans chaque prediction;
- drift des textes, labels, themes, sentiments et confiance;
- alertes et dashboards;
- persistance des metriques entre redemarrages.

### CI/CD et tests

La CI actuelle est utile, mais elle ne verifie pas les chemins les plus risques:

- pas de test de non-regression sur les metriques;
- pas de test qui preserve la verite terrain;
- pas de test du contrat frontend/API;
- pas de smoke test du bundle Hugging Face;
- pas de build des cinq Dockerfiles de services;
- pas de test d'integration Compose;
- pas de lint, type check, couverture, scan de dependances ou scan d'image;
- pas de test de charge ou de latence;
- pas de deploiement automatise et versionne vers Hugging Face.

### Documentation

La documentation doit etre resynchronisee:

- le monitoring est deja expose en format Prometheus;
- les dependances sont bornees, mais pas verrouillees exactement;
- l'architecture online est annoncee comme complete, alors que le bundle API est casse;
- la documentation ne distingue pas assez demo, staging et production.

## Architecture cible recommandee

```text
Source Trustpilot / export controle / CSV
                |
                v
        Ingestion idempotente
                |
                v
  Stockage objet prive et immuable (raw)
                |
                +------> Quarantaine + raisons de rejet
                |
                v
 Validation de schema et qualite
                |
                v
 Dataset curate versionne + splits geles
                |
                v
 Training deterministe + evaluation independante
                |
                v
 MLflow Tracking + Model Registry + gates de promotion
                |
                v
 Modele promu par version immuable
                |
                v
 API d'inference unique
        |                       |
        v                       v
 Streamlit / frontend      Monitoring / logs / alertes
        |
        v
 Feedback et revue humaine versionnes
```

Principes:

- L'API est l'unique point d'entree d'inference.
- Les frontends ne chargent jamais les modeles.
- Le dataset de test est immuable et jamais utilise pour entrainer.
- Une version modele pointe vers une version dataset, un commit Git et un manifest.
- Une promotion est basee sur des gates explicites et un rollback est possible.
- Les donnees potentiellement personnelles restent dans un stockage prive.

## Integrations necessaires

### Obligatoires pour la phase finale

1. **Validation de donnees**
   - Integrer `Pandera` pour un contrat leger et proche de pandas.
   - Valider schema, types, valeurs autorisees, unicite, texte non vide et taille maximale.
   - Produire un rapport de qualite et une quarantaine.

2. **Versionnement et stockage des datasets**
   - Utiliser un stockage objet prive: S3, Azure Blob, GCS ou MinIO local.
   - Ajouter DVC pour versionner les snapshots sans committer les donnees dans Git.
   - Pour des donnees publiques et sans PII, un repo Hugging Face Dataset prive peut etre une
     alternative, mais il ne doit pas devenir la cible par defaut pour des avis clients sensibles.

3. **Tracking et registry solides**
   - Conserver MLflow.
   - Remplacer SQLite par PostgreSQL pour un environnement partage.
   - Stocker les artefacts MLflow dans le meme stockage objet prive.
   - Logger les inputs dataset, les hashes, le commit Git, les parametres, les metriques et le
     manifest.

4. **Orchestration**
   - Ajouter un workflow GitHub Actions manuel et planifie pour:
     `ingest -> validate -> train -> evaluate -> register`.
   - Garder la promotion separee et soumise a validation.
   - Prefect peut etre ajoute plus tard si les pipelines deviennent frequents ou complexes.

5. **Deploiement et contrats**
   - Corriger le bundle Hugging Face et ajouter un smoke test.
   - Pinner le repo modele a une revision immuable.
   - Ajouter des tests de contrat entre API, Streamlit et frontend statique.
   - Faire consommer l'API par Streamlit.

6. **Securite et secrets**
   - Utiliser GitHub Secrets et Hugging Face Secrets.
   - Ne jamais stocker ou demander une cle partagee dans un frontend public.
   - Restreindre CORS, trusted hosts et documentation en environnement partage.
   - Placer MLflow, data et monitoring sur un reseau interne ou derriere une authentification.

7. **Observabilite**
   - Brancher Prometheus et Grafana.
   - Ajouter logs JSON, correlation ID, latence, erreurs, version modele et alertes.
   - Ajouter un suivi des distributions et du drift.

8. **Boucle de feedback**
   - Stocker les cas `needs_human_review` et les corrections humaines.
   - Versionner les labels corriges et leur provenance.
   - Reinjecter uniquement des donnees validees dans un prochain cycle d'entrainement.

### A ne pas ajouter sans besoin prouve

- Un feature store n'est pas necessaire pour ce POC NLP base sur du texte brut.
- Airflow est probablement trop lourd tant que GitHub Actions ou Prefect suffisent.
- Une promotion totalement automatique ne doit pas etre activee avant d'avoir un vrai dataset de
  test et des seuils metier valides.

## Best practices data a appliquer

### Contrat de donnees

Le contrat doit etre versionne dans le depot, par exemple sous `data/contracts/reviews_v1.py` ou
`data/contracts/reviews_v1.yaml`.

Champs minimaux:

| Champ | Regle |
| --- | --- |
| `review_id` | Obligatoire, non vide, unique dans un snapshot. |
| `review_title` | Optionnel, chaine normalisee. |
| `review_body` | Obligatoire, non vide, taille bornee. |
| `sentiment_label` | Enum explicite: negative, neutral, positive. |
| `theme_livraison` | Booleen ou entier 0/1. |
| `theme_sav` | Booleen ou entier 0/1. |
| `theme_produit` | Booleen ou entier 0/1. |
| `language` | Langue detectee ou declaree, avec gate sur l'anglais. |
| `source` | Origine de la review. |
| `extracted_at` | Date d'extraction UTC. |
| `taxonomy_version` | Version des regles de labellisation. |
| `split` | train, validation ou test, stable dans le temps. |

Si le sentiment par theme reste dans le produit, ajouter des labels dedies par theme et documenter
le cas ou un theme n'est pas present.

### Zones et immutabilite

- `raw`: copie immuable de la source, jamais modifiee.
- `quarantine`: lignes rejetees avec raison.
- `processed`: nettoyage deterministe, sans labels inventes silencieusement.
- `validated`: donnees conformes au contrat.
- `splits`: snapshots train, validation et test geles.
- `registry`: manifests et lineage, sans donnees sensibles.

### Manifest de dataset

Chaque dataset doit avoir un manifest contenant:

- dataset version et schema version;
- source et date d'extraction;
- checksum SHA-256 du fichier source et des sorties;
- nombre de lignes ingerees, valides, rejetees et dedupliquees;
- distribution des labels et des themes;
- langue et taux de texte vide;
- raisons de rejet;
- statut PII, licence, retention et proprietaire;
- chemin ou URI de stockage;
- commit Git et run pipeline.

### Qualite et splits

- Rejeter explicitement les colonnes manquantes au lieu de les creer silencieusement pour le
  training.
- Conserver les raisons de rejet et les doublons dans la quarantaine.
- Utiliser des splits stratifies et stables, avec une seed versionnee.
- Eviter qu'une meme review ou un meme client apparaisse dans plusieurs splits.
- Garder le test set gele et hors du cycle de tuning.
- Suivre precision, recall et F1 par theme, macro F1 sentiment, matrices de confusion et calibration.
- Evaluer les sous-groupes: longueur, langue, theme, sentiment, texte ambigu et absence de theme.

### Confidentialite et conformite

- Verifier les conditions d'utilisation et la licence de la source Trustpilot.
- Definir la base legale, la retention et les droits d'acces.
- Detecter ou masquer email, telephone, adresse, numero de commande et autres PII.
- Ne pas publier de donnees sensibles dans Git, GitHub Pages ou un repo Hugging Face public.
- Prevoir suppression, correction et audit des donnees si necessaire.

## Plan de phase finale

### Lot 0 - Figer la cible et la definition de fini

Objectif: eviter de finaliser plusieurs architectures contradictoires.

Actions:

- definir la cible: demo publique, MVP partage ou production pilote;
- choisir l'API comme unique source d'inference;
- definir le proprietaire des donnees, du modele et du deploiement;
- valider les metriques et seuils metier requis;
- definir les environnements local, staging et production.

Livrable:

- une page de decision d'architecture et une checklist de release.

Critere d'acceptation:

- aucune ambiguite sur la source de verite des donnees, modeles et predictions.

### Lot 1 - Retablir la fiabilite des metriques

Priorite: **P0**

Actions:

- conserver les colonnes de verite terrain avec un prefixe `true_`;
- conserver les predictions avec un prefixe `pred_` ou dans une structure separee;
- ajouter des tests qui echouent volontairement sur une mauvaise prediction;
- recalculer tous les rapports et runs MLflow;
- creer un vrai split train, validation et test;
- corriger la semantique du sentiment par theme;
- ajouter macro F1, metriques par classe, matrices de confusion et calibration.

Livrables:

- module d'evaluation corrige;
- dataset de test versionne;
- rapport de reference fiable;
- tests de non-regression modele.

Criteres d'acceptation:

- les metriques baissent lorsqu'une prediction est volontairement fausse;
- le test set n'est jamais utilise par la pipeline d'entrainement;
- aucune promotion n'est possible sans rapport valide.

### Lot 2 - Corriger les integrations de deploiement

Priorite: **P0**

Actions:

- ajouter `manifest.json` aux artefacts telecharges depuis Hugging Face;
- ajouter `security.py` au bundle API;
- pinner `HF_MODEL_REVISION` sur un commit immuable;
- verifier les checksums avant chargement `joblib`;
- corriger le contrat d'evaluation du frontend statique;
- faire consommer l'API par Streamlit;
- ajouter un smoke test du bundle Hugging Face et des frontends;
- construire tous les Dockerfiles dans la CI.

Livrables:

- bundle API reconstructible;
- frontend Streamlit client de l'API;
- tests de contrat et smoke tests.

Criteres d'acceptation:

- un environnement propre peut reconstruire et lancer le Space API;
- les trois frontends affichent la meme prediction pour la meme review;
- une version modele exacte est visible dans `/health`.

### Lot 3 - Solidifier la fondation data

Priorite: **P1**

Actions:

- ajouter un contrat Pandera versionne;
- produire une quarantaine et des raisons de rejet;
- ajouter checksums, manifests et lineage;
- versionner les datasets avec DVC et un stockage objet;
- ajouter langue, source, dates, taxonomie, PII et retention;
- rendre l'ingestion idempotente et le registre atomique;
- ajouter des tests de qualite et de distribution.

Livrables:

- contrat data;
- manifests enrichis;
- snapshots versionnes;
- rapport de qualite par ingestion.

Criteres d'acceptation:

- chaque modele peut etre relie a un dataset immuable;
- chaque ligne rejetee a une raison;
- aucune donnee sensible n'est publiee par defaut.

### Lot 4 - Mettre en place le cycle MLOps de promotion

Priorite: **P1**

Actions:

- rendre le training deterministe avec seed et versions exactes;
- enrichir le manifest modele avec hashes, versions, commit et dataset;
- logger les datasets comme inputs MLflow;
- definir un workflow candidat -> validation -> promotion -> rollback;
- comparer le candidat au modele actuellement promu;
- publier la revision promue vers Hugging Face ou la plateforme cible.

Livrables:

- workflow de promotion;
- manifest modele complet;
- runbook de rollback.

Criteres d'acceptation:

- un modele ne peut pas etre promu sans depasser les gates convenus;
- le modele precedent peut etre restaure rapidement;
- la source de verite modele est unique.

### Lot 5 - Durcir securite, observabilite et operations

Priorite: **P1**

Actions:

- restreindre CORS, hosts, docs et acces aux services internes;
- migrer MLflow vers PostgreSQL et stockage objet;
- utiliser une authentification adaptee ou un API gateway;
- externaliser le rate limiting si plusieurs replicas sont prevus;
- ajouter logs JSON, correlation ID, latence, erreurs et version modele;
- brancher Prometheus, Grafana et alertes;
- documenter sauvegarde, restauration, incident et cold start.

Livrables:

- configuration staging securisee;
- dashboards et alertes;
- runbook d'exploitation.

Criteres d'acceptation:

- les services internes ne sont pas publics sans besoin;
- une erreur, une regression ou un drift peut etre detecte et investigue;
- les secrets ne sont jamais presents dans Git ou un navigateur public.

### Lot 6 - Preparer les preuves finales

Priorite: **P1**

Actions:

- resynchroniser README, guides et livrables;
- generer un rapport final depuis le test set gele;
- documenter les limites et les choix;
- preparer une demo reproductible et un scenario de rollback;
- ajouter une matrice de tracabilite: exigence -> code -> test -> preuve.

Livrables:

- documentation finale;
- rapport d'evaluation fiable;
- checklist de release et de soutenance.

Criteres d'acceptation:

- chaque affirmation de qualite est reliee a une preuve reproductible;
- la demo peut etre relancee sur une machine propre.

## Definition de fini recommandee

La phase finale est terminee lorsque:

- aucun blocage P0 ne reste ouvert;
- les metriques sont calculees sur un test set immuable et independant;
- les contrats data et API sont testes;
- le bundle Hugging Face et tous les services Docker sont testes en CI;
- le modele charge est identifie par une revision immuable et un hash;
- Streamlit et les frontends utilisent l'API comme source unique;
- les donnees, runs MLflow et modeles sont relies par lineage;
- les services partages sont securises et les secrets externalises;
- un dashboard, des alertes et un runbook de rollback existent;
- la documentation correspond au comportement reel du projet.

## Ordre de travail recommande

1. Corriger l'evaluation et les tests de metriques.
2. Clarifier les labels de sentiment par theme et creer les splits.
3. Corriger Hugging Face, le contrat frontend et le cablage Streamlit.
4. Ajouter le contrat data, les manifests et le stockage versionne.
5. Mettre en place les gates MLflow et le workflow de promotion.
6. Durcir securite, observabilite et operations.
7. Regenerer toutes les preuves et la documentation finale.
