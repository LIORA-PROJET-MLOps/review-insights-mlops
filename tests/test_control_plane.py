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

    data_models = next(
        dashboard for dashboard in dashboards if dashboard["uid"] == "review-insights-data-models"
    )
    metric_panels = [panel for panel in data_models["panels"] if panel["id"] != 9]
    assert all(panel["targets"][0].get("instant") is True for panel in metric_panels)


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


def test_dagster_artifact_storage_uses_the_shared_volume():
    dagster_config = yaml.safe_load(Path("orchestration/dagster.yaml").read_text(encoding="utf-8"))
    compose = yaml.safe_load(Path("compose.yaml").read_text(encoding="utf-8"))

    artifact_dir = dagster_config["local_artifact_storage"]["config"]["base_dir"]
    dagster_volumes = compose["x-dagster-common"]["volumes"]

    assert artifact_dir == "/opt/dagster/storage/artifacts"
    assert "dagster_compute_logs:/opt/dagster/storage" in dagster_volumes


def test_orchestrator_image_precreates_writable_data_store_layout():
    dockerfile = Path("docker/orchestrator/Dockerfile").read_text(encoding="utf-8")

    for directory in (
        "/app/data_store/raw/incoming",
        "/app/data_store/raw/archive",
        "/app/data_store/processed",
        "/app/data_store/validated",
        "/app/data_store/quarantine",
        "/app/data_store/splits",
        "/app/data_store/registry",
    ):
        assert directory in dockerfile


def test_data_image_precreates_writable_feedback_mountpoint():
    dockerfile = Path("docker/data/Dockerfile").read_text(encoding="utf-8")

    assert "mkdir -p /app/feedback" in dockerfile
    assert "chown -R appuser:appuser /app" in dockerfile


def test_webhook_is_optional():
    assert send_webhook(None, {"event": "test"}) is False


def test_dagster_definitions_expose_final_workflows():
    dagster = pytest.importorskip("dagster")
    from orchestration.definitions import defs

    assert defs.resolve_job_def("data_pipeline_job")
    assert defs.resolve_job_def("model_training_job")
    assert defs.get_job_def("model_promotion_job")
    repository = defs.get_repository_def()
    assert repository.has_sensor_def("incoming_review_csv_sensor")
    assert repository.has_sensor_def("pipeline_failure_alert")
    assert (
        repository.get_sensor_def("pipeline_failure_alert").default_status
        == dagster.DefaultSensorStatus.RUNNING
    )
    assert repository.has_schedule_def("daily_full_pipeline_schedule")
    schedule = repository.get_schedule_def("daily_full_pipeline_schedule")
    assert schedule.job_name == "model_training_job"
    assert schedule.cron_schedule == "0 19 * * *"
    assert schedule.execution_timezone == "Europe/Paris"
    assert schedule.default_status == dagster.DefaultScheduleStatus.RUNNING


def test_daily_schedule_selects_latest_incoming_csv(tmp_path, monkeypatch):
    pytest.importorskip("dagster")
    from orchestration.definitions import _latest_incoming_csv

    older = tmp_path / "older.csv"
    newer = tmp_path / "newer.csv"
    older.write_text("review_id\nold\n", encoding="utf-8")
    newer.write_text("review_id\nnew\n", encoding="utf-8")
    older.touch()
    newer.touch()
    older_stat = older.stat()
    newer_stat = newer.stat()
    older.touch()
    newer.touch()
    older_time = min(older_stat.st_mtime_ns, newer_stat.st_mtime_ns) - 1_000_000
    newer_time = max(older_stat.st_mtime_ns, newer_stat.st_mtime_ns) + 1_000_000
    import os

    os.utime(older, ns=(older_time, older_time))
    os.utime(newer, ns=(newer_time, newer_time))
    monkeypatch.setenv("ORCHESTRATOR_INCOMING_DIR", str(tmp_path))

    assert _latest_incoming_csv() == newer


def test_daily_schedule_detects_an_already_ingested_source(tmp_path):
    pytest.importorskip("dagster")
    from orchestration.definitions import _source_already_ingested

    source = tmp_path / "incoming.csv"
    source.write_text("review_id\nr1\n", encoding="utf-8")
    data_root = tmp_path / "data"
    registry_dir = data_root / "registry"
    registry_dir.mkdir(parents=True)

    assert _source_already_ingested(source, data_root) is False

    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (registry_dir / "datasets_manifest.json").write_text(
        json.dumps({"datasets": [{"source_sha256": digest}]}),
        encoding="utf-8",
    )

    assert _source_already_ingested(source, data_root) is True


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
