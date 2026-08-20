from __future__ import annotations

import numpy as np

from pipelines.train_real_gold_variants import tune_joint_thresholds


def test_joint_threshold_tuning_returns_valid_metrics() -> None:
    truth = np.asarray(
        [
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 1],
            [0, 0, 1],
        ],
        dtype=int,
    )
    probabilities = np.asarray(
        [
            [0.9, 0.2, 0.1],
            [0.8, 0.9, 0.2],
            [0.2, 0.8, 0.9],
            [0.1, 0.3, 0.8],
        ],
        dtype=float,
    )
    thresholds, metrics = tune_joint_thresholds(probabilities, truth)
    assert thresholds.shape == (3,)
    assert metrics["exact_match"] == 1.0
    assert metrics["f1_macro"] == 1.0
