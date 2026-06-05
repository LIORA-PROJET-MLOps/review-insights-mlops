# Gouvernance data - Review Insights+

## Objectif

La couche data distingue maintenant trois niveaux:

1. Le CSV source archive, conserve pour la tracabilite.
2. Les artefacts CSV de compatibilite, pratiques pour inspection humaine.
3. Les artefacts Parquet canoniques, utilises par les pipelines de training et adaptes au versionnement DVC.

Un dataset peut etre techniquement valide sans etre pret pour un entrainement partage. Le statut
`quality_status` du manifest vaut `ready` uniquement quand toutes les regles de
`data/contracts/reviews_quality_policy_v1.json` passent.

## Artefacts par version

Une ingestion produit:

- un brut archive dans `data/raw/archive/`
- un dataset nettoye CSV et Parquet dans `data/processed/`
- un dataset valide CSV et Parquet dans `data/validated/`
- une quarantaine CSV et Parquet dans `data/quarantine/`
- une file d'annotation CSV et Parquet pour les sentiments par theme manquants
- des splits deterministes CSV et Parquet quand le volume le permet
- un rapport de qualite et un manifest avec checksums dans `data/registry/`

Les labels de sentiment par theme ne sont jamais inventes. Une review associee a un theme sans
`sentiment_<theme>` reste techniquement valide, mais elle est ajoutee a la file d'annotation et fait
echouer la gate de couverture explicite.

## Regles de qualite

La politique versionnee controle notamment:

- volume total valide
- volume minimal par classe de sentiment
- volume minimal par theme
- taux maximal de lignes rejetees
- detection probable de PII
- detection probable de texte hors scope anglais
- couverture des labels de sentiment explicites par theme

Les controles PII et langue sont des heuristiques de screening. Ils signalent les lignes a examiner,
mais ne remplacent ni un outil DLP ni une validation humaine.

## Mode strict

L'ingestion standard ecrit les artefacts de diagnostic meme si le dataset n'est pas pret:

```powershell
py -3 pipelines/ingest_csv_dataset.py data/sample/reviews_poc_test.csv --dataset-version poc_reference_v1
```

Le mode strict ecrit les diagnostics puis retourne une erreur si une gate echoue:

```powershell
py -3 pipelines/ingest_csv_dataset.py data/sample/reviews_poc_test.csv `
  --dataset-version candidate_v1 `
  --enforce-quality-gates
```

Le retraining partage doit utiliser ce mode strict.

## Annotation

Pour preparer un paquet portable pour annotateurs:

```powershell
py -3 pipelines/prepare_annotation_batch.py data/sample/reviews_poc_test.csv `
  --dataset-version annotation_poc_40 `
  --output-dir artifacts/annotation_batches/annotation_poc_40
```

Le guide d'annotation theme/sentiment est `docs/ANNOTATION_GUIDE_FR.md`.

## Versionnement DVC

DVC est initialise avec un remote local `localstore` pour verifier le workflow sans credentials.
Ce remote est un support de developpement, pas un stockage partage.

Installation:

```powershell
py -3 -m pip install -r requirements-data-versioning.txt
```

Commandes usuelles:

```powershell
dvc status
dvc push
dvc pull
```

Pour un environnement partage, remplacer le remote par un bucket S3 ou un endpoint compatible S3
tel que MinIO:

```powershell
.\scripts\configure_dvc_remote.ps1 -Name storage -Url s3://review-insights-data -Default
dvc remote modify --local storage endpointurl https://object-storage.example.com
```

Les credentials doivent toujours etre ajoutes avec `--local`, donc dans `.dvc/config.local` ignore
par Git.

## Critere de sortie phase 1

La phase data est techniquement terminee quand:

- l'ingestion produit les artefacts canoniques et leurs checksums
- le rapport de qualite est reproductible
- les labels manquants sont visibles dans la file d'annotation
- le mode strict bloque un dataset non pret
- le workflow DVC `status`, `push` et `pull` est fonctionnel

La collecte d'un dataset plus large et son annotation metier restent des travaux humains necessaires
avant de pouvoir obtenir un statut `ready`.
