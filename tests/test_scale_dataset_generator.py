from pathlib import Path

from pipelines.generate_scale_datasets import DEFAULT_SPECS, generate_dataset, write_scale_datasets


def test_each_scale_profile_is_valid_and_deterministic():
    required_columns = {
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
    }
    for default_spec in DEFAULT_SPECS:
        spec = type(default_spec)(
            name=default_spec.name,
            rows=600,
            seed=default_spec.seed,
            description=default_spec.description,
        )
        first = generate_dataset(spec)
        second = generate_dataset(spec)

        assert first.equals(second)
        assert set(first.columns) == required_columns
        assert first["review_id"].is_unique
        assert first["review_body"].is_unique
        assert set(first["sentiment_label"]) == {"negative", "neutral", "positive"}
        assert all(first[f"theme_{theme}"].sum() >= 10 for theme in ("livraison", "sav", "produit"))
        for theme in ("livraison", "sav", "produit"):
            present = first[f"theme_{theme}"].eq(1)
            assert first.loc[present, f"sentiment_{theme}"].isin(
                {"negative", "neutral", "positive"}
            ).all()


def test_scale_dataset_manifest_records_three_datasets(tmp_path: Path):
    manifest = write_scale_datasets(tmp_path, rows_per_dataset=300)

    assert manifest["total_rows"] == 900
    assert len(manifest["datasets"]) == 3
    assert Path(manifest["manifest_path"]).exists()
    for dataset in manifest["datasets"]:
        assert Path(dataset["path"]).exists()
        assert dataset["profile"]["duplicate_review_ids"] == 0
        assert dataset["profile"]["duplicate_texts"] == 0
