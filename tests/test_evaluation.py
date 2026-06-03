import pandas as pd

from src.review_insights.evaluation import evaluate_predictions


def test_theme_metrics_use_preserved_ground_truth():
    predictions = pd.DataFrame(
        [
            {
                "true_theme_livraison": 1,
                "true_theme_sav": 0,
                "true_theme_produit": 0,
                "theme_livraison": 0,
                "theme_sav": 0,
                "theme_produit": 0,
                "sentiment_label": "positive",
                "global_sentiment": "positive",
            }
        ]
    )

    summary = evaluate_predictions(predictions, backend_name="test").to_dict()

    assert summary["theme_exact_match"] == 0.0
    assert summary["theme_recall_macro"] < 1.0
