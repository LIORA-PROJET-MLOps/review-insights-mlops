from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from huggingface_hub import hf_hub_download


DEFAULT_MODEL_ID = "SebasLopez-ai/distilbert-amazon-reviews-sentiment"
DEFAULT_MODEL_REVISION = "881c6455b01b7ef50026f33902f6433651a1b1f0"
ONNX_ARTIFACT_FILES = (
    "onnx/model_quantized.onnx",
    "onnx/config.json",
    "onnx/special_tokens_map.json",
    "onnx/tokenizer.json",
    "onnx/tokenizer_config.json",
    "onnx/vocab.txt",
)
ALLOWED_LABELS = {"negative", "neutral", "positive"}


@dataclass(frozen=True)
class SentimentPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def _softmax(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=float)
    shifted = values - np.max(values)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum()


def _load_label_map(config_path: Path) -> dict[int, str]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_mapping = payload.get("id2label", {})
    label_map = {int(class_id): str(label).strip().lower() for class_id, label in raw_mapping.items()}
    if set(label_map.values()) != ALLOWED_LABELS:
        raise ValueError(
            "Transformer sentiment labels must be exactly: negative, neutral, positive."
        )
    return label_map


def predict_with_components(
    text: str,
    *,
    tokenizer: Any,
    session: Any,
    label_map: dict[int, str],
    max_length: int,
) -> SentimentPrediction:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise ValueError("Review text is required for Transformer sentiment inference.")

    encoded = tokenizer(
        normalized_text,
        return_tensors="np",
        truncation=True,
        max_length=max_length,
        padding=True,
    )
    input_names = {item.name for item in session.get_inputs()}
    inputs = {
        name: np.asarray(value, dtype=np.int64)
        for name, value in encoded.items()
        if name in input_names
    }
    if not inputs:
        raise ValueError("Tokenizer output does not match the ONNX model inputs.")

    logits = np.asarray(session.run(None, inputs)[0][0], dtype=float)
    probabilities = _softmax(logits)
    predicted_class = int(np.argmax(probabilities))
    if predicted_class not in label_map:
        raise ValueError(f"Unknown Transformer sentiment class: {predicted_class}")
    resolved = {
        label: round(float(probabilities[class_id]), 6)
        for class_id, label in label_map.items()
    }
    return SentimentPrediction(
        label=label_map[predicted_class],
        confidence=round(float(probabilities[predicted_class]), 6),
        probabilities=resolved,
    )


class OnnxSentimentBackend:
    name = "hf_onnx_sentiment_v1"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        revision: str = DEFAULT_MODEL_REVISION,
        artifacts_dir: str = ".cache/review_insights/sentiment",
        cache_dir: str = ".cache/huggingface",
        token: str | None = None,
        max_length: int = 256,
    ) -> None:
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "The optional Transformer sentiment backend requires transformers and onnxruntime."
            ) from exc

        if not revision or revision == "main":
            raise ValueError("HF_SENTIMENT_REVISION must be pinned to an immutable commit.")

        self.model_id = model_id
        self.revision = revision
        self.max_length = max_length
        safe_model_id = model_id.replace("/", "--")
        target_dir = Path(artifacts_dir) / safe_model_id / revision
        target_dir.mkdir(parents=True, exist_ok=True)

        for filename in ONNX_ARTIFACT_FILES:
            hf_hub_download(
                repo_id=model_id,
                filename=filename,
                repo_type="model",
                revision=revision,
                token=token,
                cache_dir=cache_dir,
                local_dir=target_dir,
            )

        model_dir = target_dir / "onnx"
        self._tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self._session = ort.InferenceSession(
            str(model_dir / "model_quantized.onnx"),
            providers=["CPUExecutionProvider"],
        )
        self._label_map = _load_label_map(model_dir / "config.json")

    def predict(self, text: str) -> SentimentPrediction:
        return predict_with_components(
            text,
            tokenizer=self._tokenizer,
            session=self._session,
            label_map=self._label_map,
            max_length=self.max_length,
        )
