import pandas as pd

from src.review_insights.dataset import prepare_dataset
from src.review_insights.engine import analyze_review, detect_themes, score_sentiment


def test_detect_delivery_theme():
    result = detect_themes("the delivery was late and the package arrived damaged")
    assert result["livraison"].present == 1


def test_detect_support_theme():
    result = detect_themes("customer support never answered my refund request")
    assert result["sav"].present == 1


def test_positive_sentiment():
    label, confidence, _, _ = score_sentiment("great quality and very comfortable")
    assert label == "positive"
    assert confidence > 0.5


def test_negative_sentiment():
    label, confidence, _, _ = score_sentiment("terrible support and bad refund process")
    assert label == "negative"
    assert confidence > 0.5


def test_prepare_dataset_adds_columns():
    df = prepare_dataset(pd.DataFrame({"review_body": ["late delivery"]}))
    assert "review_id" in df.columns
    assert "theme_livraison" in df.columns


def test_analyze_review_returns_theme():
    result = analyze_review("customer support was slow and never answered", "r1")
    assert "sav" in result["themes_detected"]
    assert result["global_sentiment"] == "negative"

