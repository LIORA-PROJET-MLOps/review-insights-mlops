# Evaluation du backend sentiment Transformer

Date : 29 juin 2026

## Configuration

- modele : `SebasLopez-ai/distilbert-amazon-reviews-sentiment`
- revision : `881c6455b01b7ef50026f33902f6433651a1b1f0`
- runtime : ONNX Runtime CPU
- artefact : `onnx/model_quantized.onnx`
- dataset : `data/sample/reviews_poc_test.csv`
- lignes : 40

## Resultats compares

| Metrique | Backend projet | DistilBERT ONNX | Ecart |
| --- | ---: | ---: | ---: |
| Accuracy sentiment | 0.5750 | 0.9000 | +0.3250 |
| Macro precision sentiment | 0.5389 | 0.9103 | +0.3714 |
| Macro recall sentiment | 0.5250 | 0.8857 | +0.3607 |
| Macro F1 sentiment | 0.5111 | 0.8932 | +0.3821 |
| Taux de revue humaine | 0.5000 | 0.5000 | 0.0000 |

Les metriques de themes restent identiques, car le Transformer remplace uniquement le sentiment
global. Apres mise en cache, l'initialisation mesuree est de 3,06 secondes et l'evaluation des 40
reviews prend 1,411 seconde, soit 35,3 ms par review sur la machine d'audit.

## Decision

Le backend `hf_onnx` est valide pour le staging. Le backend projet reste le fallback automatique
et le mode par defaut en local/CI. Le benchmark doit etre rejoue sur un dataset plus grand avant
une decision de production.
