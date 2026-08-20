from __future__ import annotations

import pandas as pd

from pipelines.build_real_synthetic_training_mix import _sample_balanced_sentiment


def test_balanced_sentiment_sample() -> None:
    frame = pd.DataFrame(
        {
            "sentiment_label": [label for label in ("negative", "neutral", "positive") for _ in range(10)],
            "value": list(range(30)),
        }
    )
    sampled = _sample_balanced_sentiment(frame, rows=15, seed=4)
    assert sampled["sentiment_label"].value_counts().to_dict() == {
        "negative": 5,
        "neutral": 5,
        "positive": 5,
    }
