from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
THEMES = ("livraison", "sav", "produit")
SENTIMENTS = ("negative", "neutral", "positive")


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    rows: int
    seed: int
    description: str


DEFAULT_SPECS = (
    DatasetSpec(
        name="balanced_core",
        rows=15_000,
        seed=104_729,
        description="Balanced sentiments and theme coverage with direct customer language.",
    ),
    DatasetSpec(
        name="noisy_long_tail",
        rows=15_000,
        seed=130_363,
        description="Skewed theme prevalence, mild typos, negations and long-tail wording.",
    ),
    DatasetSpec(
        name="multitheme_context",
        rows=15_000,
        seed=155_921,
        description="Mostly multi-theme reviews with longer contextual formulations.",
    ),
)


THEME_PHRASES = {
    "livraison": {
        "negative": (
            "the delivery arrived late and the parcel tracking was unreliable",
            "shipping missed the promised window and the box arrived damaged",
            "the courier delayed the order and left the package in poor condition",
            "delivery was slow and the parcel never reached the expected location",
        ),
        "neutral": (
            "the delivery arrived within the stated window without any surprise",
            "shipping followed the standard schedule and tracking was ordinary",
            "the parcel arrived as planned with average packaging",
            "delivery timing matched the estimate and nothing stood out",
        ),
        "positive": (
            "the delivery was fast and the parcel arrived in perfect condition",
            "shipping was earlier than expected and tracking updates were clear",
            "the courier handled the package carefully and arrived on time",
            "delivery was prompt with secure packaging and useful notifications",
        ),
    },
    "sav": {
        "negative": (
            "customer support ignored my request and the refund process was frustrating",
            "the service agent did not solve the issue and stopped replying",
            "support kept transferring the case without providing a useful answer",
            "the return request remained unresolved after several support messages",
        ),
        "neutral": (
            "customer support confirmed the standard policy and closed the request",
            "the service agent provided a routine answer within the normal timeframe",
            "support handled the request as expected without extra assistance",
            "the return process followed the published steps and took the usual time",
        ),
        "positive": (
            "customer support answered quickly and resolved the issue completely",
            "the service agent was helpful and arranged the refund without delay",
            "support understood the problem and offered a practical solution",
            "the return request was handled politely with clear instructions",
        ),
    },
    "produit": {
        "negative": (
            "the product quality was poor and the material felt cheap",
            "the item did not match the description and failed during normal use",
            "the product arrived with a defect and the fit was disappointing",
            "the item looked unfinished and its performance was below expectations",
        ),
        "neutral": (
            "the product matched the basic description and performed adequately",
            "the item was acceptable for the price with average material quality",
            "the product worked as described without any remarkable feature",
            "the item had a standard finish and met the minimum expectations",
        ),
        "positive": (
            "the product quality was excellent and the material felt durable",
            "the item matched the description perfectly and worked very well",
            "the product had a great finish and exceeded my expectations",
            "the item felt reliable and its performance was impressive",
        ),
    },
}

PROFILE_CONNECTORS = {
    "balanced_core": (
        "Overall, this was a clear and straightforward purchase.",
        "This summary reflects the complete order experience.",
        "The result was consistent from checkout to final use.",
    ),
    "noisy_long_tail": (
        "Even so, the full order needs to be judged on the details above.",
        "I checked the order twice before writing this honest review.",
        "This was not a simple first impression but the complete experience.",
        "In everyday use, the same result remained noticeable.",
    ),
    "multitheme_context": (
        "Taken together, these parts shaped the complete customer journey.",
        "The details matter because the order was used over several ordinary days.",
        "Across the purchase, each part contributed to the overall assessment.",
        "The final opinion considers the order, follow-up and practical use.",
    ),
}

TITLE_TEMPLATES = {
    "negative": ("Disappointing order", "Problems throughout", "Below expectations"),
    "neutral": ("Standard experience", "As expected", "Ordinary purchase"),
    "positive": ("Excellent experience", "Better than expected", "Very satisfied"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trace_letters(value: int) -> str:
    letters: list[str] = []
    current = value
    for _ in range(5):
        letters.append(chr(ord("a") + current % 26))
        current //= 26
    return " ".join(reversed(letters))


def _weighted_choice(rng: random.Random, values: Iterable[tuple[object, float]]):
    options = list(values)
    return rng.choices(
        [value for value, _ in options],
        weights=[weight for _, weight in options],
        k=1,
    )[0]


def _sentiment_for_profile(rng: random.Random, profile: str) -> str:
    weights = {
        "balanced_core": (("negative", 1), ("neutral", 1), ("positive", 1)),
        "noisy_long_tail": (("negative", 0.27), ("neutral", 0.23), ("positive", 0.50)),
        "multitheme_context": (("negative", 0.38), ("neutral", 0.24), ("positive", 0.38)),
    }
    return str(_weighted_choice(rng, weights[profile]))


def _themes_for_profile(rng: random.Random, profile: str) -> tuple[str, ...]:
    if profile == "balanced_core":
        size = int(_weighted_choice(rng, ((1, 0.62), (2, 0.33), (3, 0.05))))
        return tuple(sorted(rng.sample(THEMES, size)))
    if profile == "noisy_long_tail":
        first = str(
            _weighted_choice(
                rng,
                (("produit", 0.58), ("livraison", 0.29), ("sav", 0.13)),
            )
        )
        if rng.random() < 0.22:
            second = rng.choice([theme for theme in THEMES if theme != first])
            return tuple(sorted((first, second)))
        return (first,)
    size = int(_weighted_choice(rng, ((1, 0.12), (2, 0.63), (3, 0.25))))
    return tuple(sorted(rng.sample(THEMES, size)))


def _apply_mild_noise(text: str, rng: random.Random) -> str:
    replacements = {
        "delivery": "delivry",
        "shipping": "shiping",
        "support": "suppport",
        "product": "produckt",
        "package": "packge",
    }
    if rng.random() < 0.36:
        available = [word for word in replacements if word in text]
        if available:
            source = rng.choice(available)
            text = text.replace(source, replacements[source], 1)
    if rng.random() < 0.25:
        text = text.replace(" and ", " - and ", 1)
    return text


def generate_dataset(spec: DatasetSpec) -> pd.DataFrame:
    if spec.name not in PROFILE_CONNECTORS:
        raise ValueError(f"Unknown dataset profile: {spec.name}")
    if spec.rows < 300:
        raise ValueError("At least 300 rows are required for a scale dataset.")

    rng = random.Random(spec.seed)
    rows: list[dict[str, object]] = []
    for index in range(spec.rows):
        sentiment = _sentiment_for_profile(rng, spec.name)
        active_themes = _themes_for_profile(rng, spec.name)
        phrases = [rng.choice(THEME_PHRASES[theme][sentiment]) for theme in active_themes]
        rng.shuffle(phrases)
        body = ". ".join(phrase.capitalize() for phrase in phrases) + "."
        body += " " + rng.choice(PROFILE_CONNECTORS[spec.name])
        if spec.name == "noisy_long_tail":
            body = _apply_mild_noise(body, rng)
        body += f" Trace {_trace_letters(index)}."

        row: dict[str, object] = {
            "review_id": f"scale-{spec.name}-{index + 1:06d}",
            "review_title": rng.choice(TITLE_TEMPLATES[sentiment]),
            "review_body": body,
            "sentiment_label": sentiment,
        }
        for theme in THEMES:
            present = int(theme in active_themes)
            row[f"theme_{theme}"] = present
            row[f"sentiment_{theme}"] = sentiment if present else ""
        rows.append(row)

    rng.shuffle(rows)
    return pd.DataFrame(rows)


def _dataset_profile(df: pd.DataFrame) -> dict[str, object]:
    text = df["review_title"].astype(str).str.cat(df["review_body"].astype(str), sep=" ")
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "duplicate_review_ids": int(df["review_id"].duplicated().sum()),
        "duplicate_texts": int(text.duplicated().sum()),
        "empty_review_bodies": int(df["review_body"].astype(str).str.strip().eq("").sum()),
        "sentiment_distribution": {
            str(key): int(value)
            for key, value in df["sentiment_label"].value_counts().sort_index().items()
        },
        "theme_counts": {
            theme: int(df[f"theme_{theme}"].sum())
            for theme in THEMES
        },
        "multi_theme_rows": int((df[[f"theme_{theme}" for theme in THEMES]].sum(axis=1) > 1).sum()),
        "mean_body_characters": round(float(df["review_body"].str.len().mean()), 2),
    }


def write_scale_datasets(
    output_dir: Path,
    *,
    rows_per_dataset: int,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, object]] = []
    for default_spec in DEFAULT_SPECS:
        spec = DatasetSpec(
            name=default_spec.name,
            rows=rows_per_dataset,
            seed=default_spec.seed,
            description=default_spec.description,
        )
        df = generate_dataset(spec)
        path = output_dir / f"reviews_scale_{spec.name}_{rows_per_dataset}.csv"
        df.to_csv(path, index=False)
        generated.append(
            {
                "spec": asdict(spec),
                "path": _portable_path(path),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "profile": _dataset_profile(df),
            }
        )

    manifest = {
        "schema_version": "1.0.0",
        "generator": _portable_path(Path(__file__)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": rows_per_dataset * len(DEFAULT_SPECS),
        "datasets": generated,
    }
    manifest_path = output_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {**manifest, "manifest_path": _portable_path(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate three deterministic, labeled Review Insights scale datasets."
    )
    parser.add_argument(
        "--rows-per-dataset",
        type=int,
        default=15_000,
        help="Rows generated for each of the three profiles.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "data" / "generated"),
    )
    args = parser.parse_args()
    result = write_scale_datasets(
        Path(args.output_dir),
        rows_per_dataset=args.rows_per_dataset,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
