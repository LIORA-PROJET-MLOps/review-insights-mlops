# Rapport release modele

- Date UTC: 2026-08-20T10:26:55.778496+00:00
- Statut gates: `approved`
- Evaluation: `reports/real_mixed_cycle/blind_test_hybrid_lr_c4.json`
- Policy: `config/model_promotion_policy_poc_real_v2.json`
- Manifest modele: `artifacts/real_mixed_models/hybrid_lr_c4/manifest.json`

## Checks echoues

[]

## Candidate metrics

{
  "rows": 150.0,
  "sentiment_accuracy": 0.86,
  "sentiment_macro_precision": 0.8653,
  "sentiment_macro_recall": 0.8428,
  "sentiment_macro_f1": 0.8473,
  "sentiment_evaluated_rows": 150.0,
  "theme_exact_match": 0.66,
  "theme_precision_macro": 0.8895,
  "theme_recall_macro": 0.8032,
  "theme_f1_macro": 0.8359,
  "human_review_rate": 0.02
}

## Checks

{
  "minimum_rows": {
    "passed": true,
    "actual": 150.0,
    "operator": ">=",
    "threshold": 150.0
  },
  "minimum_sentiment_accuracy": {
    "passed": true,
    "actual": 0.86,
    "operator": ">=",
    "threshold": 0.82
  },
  "minimum_sentiment_macro_f1": {
    "passed": true,
    "actual": 0.8473,
    "operator": ">=",
    "threshold": 0.8
  },
  "minimum_theme_exact_match": {
    "passed": true,
    "actual": 0.66,
    "operator": ">=",
    "threshold": 0.62
  },
  "minimum_theme_precision_macro": {
    "passed": true,
    "actual": 0.8895,
    "operator": ">=",
    "threshold": 0.85
  },
  "minimum_theme_recall_macro": {
    "passed": true,
    "actual": 0.8032,
    "operator": ">=",
    "threshold": 0.78
  },
  "minimum_theme_f1_macro": {
    "passed": true,
    "actual": 0.8359,
    "operator": ">=",
    "threshold": 0.82
  },
  "maximum_human_review_rate": {
    "passed": true,
    "actual": 0.02,
    "operator": "<=",
    "threshold": 0.1
  }
}
