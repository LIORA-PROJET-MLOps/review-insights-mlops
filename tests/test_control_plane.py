import json
from pathlib import Path

import pytest
import yaml

from orchestration.alerts import send_webhook


def test_provisioned_grafana_dashboards_are_valid_and_unique():
    dashboard_paths = sorted(Path("deploy/grafana/dashboards").glob("*.json"))
    dashboards = [json.loads(path.read_text(encoding="utf-8")) for path in dashboard_paths]

    assert len(dashboards) == 4
    assert len({dashboard["uid"] for dashboard in dashboards}) == 4
    assert all(dashboard["panels"] for dashboard in dashboards)


def test_control_plane_yaml_files_are_valid():
    paths = [
        Path("deploy/prometheus/prometheus.yml"),
        Path("deploy/prometheus/rules/review-insights.yml"),
        Path("deploy/alertmanager/alertmanager.yml"),
        Path("deploy/blackbox/blackbox.yml"),
        Path("deploy/grafana/provisioning/datasources/prometheus.yml"),
        Path("deploy/grafana/provisioning/dashboards/dashboards.yml"),
        Path("orchestration/workspace.yaml"),
        Path("orchestration/dagster.yaml"),
    ]

    assert all(yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths)


def test_webhook_is_optional():
    assert send_webhook(None, {"event": "test"}) is False


def test_dagster_definitions_expose_final_workflows():
    pytest.importorskip("dagster")
    from orchestration.definitions import defs

    assert defs.resolve_job_def("data_pipeline_job")
    assert defs.resolve_job_def("model_training_job")
    assert defs.get_job_def("model_promotion_job")
    repository = defs.get_repository_def()
    assert repository.has_sensor_def("incoming_review_csv_sensor")
    assert repository.has_sensor_def("pipeline_failure_alert")


def test_dagster_data_pipeline_executes_existing_ingestion(tmp_path):
    pytest.importorskip("dagster")
    from orchestration.definitions import defs

    result = defs.resolve_job_def("data_pipeline_job").execute_in_process(
        run_config={
            "ops": {
                "ingested_review_dataset": {
                    "config": {
                        "source_csv": "data/sample/reviews_poc_test.csv",
                        "data_root": str(tmp_path),
                        "dataset_version": "dagster_test",
                    }
                }
            }
        }
    )

    assert result.success is True
    assert (tmp_path / "registry" / "dataset_dagster_test.json").exists()
