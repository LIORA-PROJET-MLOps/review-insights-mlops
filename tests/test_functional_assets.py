from pathlib import Path

import pandas as pd


def test_functional_test_dataset_covers_core_cases():
    df = pd.read_csv("data/sample/reviews_functional_test.csv")

    assert len(df) >= 10
    assert {
        "review_id",
        "review_title",
        "review_body",
        "sentiment_label",
        "theme_livraison",
        "theme_sav",
        "theme_produit",
        "sentiment_livraison",
        "sentiment_sav",
        "sentiment_produit",
    }.issubset(df.columns)
    assert set(df["sentiment_label"]) == {"negative", "neutral", "positive"}
    assert int(df["theme_livraison"].sum()) > 0
    assert int(df["theme_sav"].sum()) > 0
    assert int(df["theme_produit"].sum()) > 0


def test_functional_smoke_script_exists():
    script = Path("scripts/run_functional_smoke_tests.ps1")

    assert script.exists()
    assert "Functional smoke tests passed" in script.read_text(encoding="utf-8")
