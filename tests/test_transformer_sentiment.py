import json
from pathlib import Path

import numpy as np
import pytest

from src.review_insights.transformer_sentiment import (
    _load_label_map,
    predict_with_components,
)


class _Input:
    def __init__(self, name: str) -> None:
        self.name = name


class _Tokenizer:
    def __call__(self, *_args, **_kwargs):
        return {
            "input_ids": np.asarray([[101, 2023, 102]]),
            "attention_mask": np.asarray([[1, 1, 1]]),
            "ignored_input": np.asarray([[0, 0, 0]]),
        }


class _Session:
    def get_inputs(self):
        return [_Input("input_ids"), _Input("attention_mask")]

    def run(self, _outputs, inputs):
        assert set(inputs) == {"input_ids", "attention_mask"}
        return [np.asarray([[-2.0, 0.5, 3.0]])]


def test_predict_with_components_maps_probabilities():
    prediction = predict_with_components(
        "A genuinely excellent product.",
        tokenizer=_Tokenizer(),
        session=_Session(),
        label_map={0: "negative", 1: "neutral", 2: "positive"},
        max_length=256,
    )

    assert prediction.label == "positive"
    assert prediction.confidence > 0.9
    assert set(prediction.probabilities) == {"negative", "neutral", "positive"}


def test_predict_with_components_rejects_empty_text():
    with pytest.raises(ValueError, match="Review text is required"):
        predict_with_components(
            " ",
            tokenizer=_Tokenizer(),
            session=_Session(),
            label_map={0: "negative", 1: "neutral", 2: "positive"},
            max_length=256,
        )


def test_load_label_map_requires_expected_classes(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"id2label": {"0": "bad", "1": "good"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="must be exactly"):
        _load_label_map(config_path)
