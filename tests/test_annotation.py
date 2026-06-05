import shutil
from pathlib import Path

import pandas as pd

from src.review_insights.annotation import prepare_annotation_batch


def test_prepare_annotation_batch_exports_queue_and_readiness_report():
    work_dir = Path("tests_runtime/annotation_batch")
    if work_dir.exists():
        shutil.rmtree(work_dir)

    result = prepare_annotation_batch(
        Path("data/sample/reviews_poc_test.csv"),
        data_root=work_dir / "data",
        dataset_version="annotation_test",
        output_dir=work_dir / "batch",
    )

    queue_path = Path(result.annotation_queue_path)
    report_path = Path(result.readiness_report_path)
    queue = pd.read_csv(queue_path)

    assert result.dataset_version == "annotation_test"
    assert result.annotation_queue_rows == len(queue)
    assert result.annotation_queue_rows > 0
    assert queue_path.exists()
    assert report_path.exists()
    assert "Rapport readiness dataset" in report_path.read_text(encoding="utf-8")
    assert result.quality_status == "not_ready"

    shutil.rmtree(work_dir)
