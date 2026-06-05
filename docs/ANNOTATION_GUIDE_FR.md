# Guide d'annotation theme/sentiment

## Objectif

Ce guide sert a completer les labels de sentiment par theme pour les reviews client.

Le contrat data accepte les colonnes:

- `sentiment_livraison`
- `sentiment_sav`
- `sentiment_produit`

Ces labels sont necessaires pour entrainer de vrais modeles de sentiment par theme. Sans eux, la
pipeline utilise encore le sentiment global comme fallback limite.

## Valeurs autorisees

Utiliser uniquement:

- `negative`
- `neutral`
- `positive`

## Regles simples

- Annoter le sentiment du theme demande, pas le sentiment global de la review.
- Si le theme est mentionne avec un probleme clair, mettre `negative`.
- Si le theme est mentionne avec une satisfaction claire, mettre `positive`.
- Si le theme est factuel, ambigu ou melange, mettre `neutral`.
- Ne pas inventer un sentiment absent du texte.

## Exemples

| Theme | Texte | Label |
| --- | --- | --- |
| livraison | `The parcel arrived two days early.` | `positive` |
| livraison | `The estimated delivery date was missed.` | `negative` |
| sav | `Support replied within an hour and solved my issue.` | `positive` |
| sav | `Customer service never answered my refund request.` | `negative` |
| produit | `The material feels premium.` | `positive` |
| produit | `The size is completely wrong.` | `negative` |
| produit | `The product is okay but nothing special.` | `neutral` |

## Commande

Generer une file d'annotation depuis un CSV:

```powershell
py -3 pipelines/prepare_annotation_batch.py data/sample/reviews_poc_test.csv `
  --dataset-version annotation_poc_40 `
  --output-dir artifacts/annotation_batches/annotation_poc_40
```

Le fichier `annotation_queue_<version>.csv` contient une ligne par couple `review_id` / theme a
annoter. Completer uniquement la colonne `sentiment_label`.
