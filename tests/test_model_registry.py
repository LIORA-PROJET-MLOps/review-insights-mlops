import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.review_insights.model_registry import (
    DEFAULT_PROMOTION_POLICY_PATH,
    PromotionPolicy,
    deploy_run_model_artifacts,
    evaluate_promotion_gates,
    load_promotion_policy,
    promote_candidate,
    rollback_champion,
)
from src.review_insights.model_backend import ARTIFACT_FILENAMES


POLICY = PromotionPolicy(
    policy_version="test",
    registered_model_name="review-insights-project-models",
    candidate_alias="candidate",
    champion_alias="champion",
    previous_champion_alias="previous_champion",
    required_metrics={
        "rows": 30.0,
        "sentiment_accuracy": 0.55,
        "theme_exact_match": 0.65,
    },
    max_metric_regression={
        "sentiment_accuracy": 0.02,
        "theme_exact_match": 0.02,
    },
)


class FakeClient:
    def __init__(self, versions, aliases, metrics):
        self.versions = {str(version.version): version for version in versions}
        self.aliases = dict(aliases)
        self.metrics = metrics
        self.version_tags = []
        self.model_tags = []

    def get_model_version(self, _name, version):
        return self.versions[str(version)]

    def get_model_version_by_alias(self, _name, alias):
        if alias not in self.aliases:
            raise KeyError(alias)
        return self.versions[str(self.aliases[alias])]

    def get_run(self, run_id):
        return SimpleNamespace(data=SimpleNamespace(metrics=self.metrics[run_id]))

    def set_registered_model_alias(self, _name, alias, version):
        self.aliases[alias] = str(version)

    def delete_registered_model_alias(self, _name, alias):
        self.aliases.pop(alias, None)

    def set_model_version_tag(self, name, version, key, value):
        self.version_tags.append((name, str(version), key, value))

    def set_registered_model_tag(self, name, key, value):
        self.model_tags.append((name, key, value))


def _version(version: str, run_id: str):
    return SimpleNamespace(version=version, run_id=run_id)


def test_evaluate_promotion_gates_rejects_regression():
    report = evaluate_promotion_gates(
        {
            "rows": 40.0,
            "sentiment_accuracy": 0.70,
            "theme_exact_match": 0.70,
        },
        {
            "rows": 40.0,
            "sentiment_accuracy": 0.75,
            "theme_exact_match": 0.70,
        },
        POLICY,
    )

    assert report["status"] == "rejected"
    assert report["failed_checks"] == ["max_regression_sentiment_accuracy"]


def test_evaluate_promotion_gates_supports_maximum_metrics():
    policy = PromotionPolicy(
        policy_version="test",
        registered_model_name="review-insights-project-models",
        candidate_alias="candidate",
        champion_alias="champion",
        previous_champion_alias="previous_champion",
        required_metrics={"rows": 30.0},
        maximum_metrics={"human_review_rate": 0.5},
        max_metric_regression={},
    )

    report = evaluate_promotion_gates(
        {"rows": 40.0, "human_review_rate": 0.75},
        None,
        policy,
    )

    assert report["status"] == "rejected"
    assert report["failed_checks"] == ["maximum_human_review_rate"]


def test_default_promotion_policy_loads_f1_and_maximum_gates():
    policy = load_promotion_policy(DEFAULT_PROMOTION_POLICY_PATH)

    assert "sentiment_macro_f1" in policy.required_metrics
    assert "theme_f1_macro" in policy.required_metrics
    assert policy.maximum_metrics["human_review_rate"] == 0.6


def test_promote_candidate_bootstraps_champion_and_writes_report(tmp_path: Path):
    candidate = _version("2", "run_candidate")
    client = FakeClient(
        [candidate],
        {"candidate": "2"},
        {
            "run_candidate": {
                "rows": 40.0,
                "sentiment_accuracy": 0.60,
                "theme_exact_match": 0.70,
            }
        },
    )
    report_path = tmp_path / "promotion.json"

    result = promote_candidate(client, policy=POLICY, report_path=report_path)

    assert result.status == "promoted"
    assert result.champion_version == "2"
    assert result.previous_champion_version is None
    assert client.aliases["champion"] == "2"
    assert json.loads(report_path.read_text(encoding="utf-8"))["gate_report"]["bootstrap_promotion"] is True


def test_promote_candidate_preserves_previous_champion(tmp_path: Path):
    champion = _version("1", "run_champion")
    candidate = _version("2", "run_candidate")
    client = FakeClient(
        [champion, candidate],
        {"champion": "1", "candidate": "2"},
        {
            "run_champion": {
                "rows": 40.0,
                "sentiment_accuracy": 0.60,
                "theme_exact_match": 0.70,
            },
            "run_candidate": {
                "rows": 40.0,
                "sentiment_accuracy": 0.61,
                "theme_exact_match": 0.71,
            },
        },
    )

    result = promote_candidate(client, policy=POLICY, report_path=tmp_path / "promotion.json")

    assert result.status == "promoted"
    assert client.aliases["champion"] == "2"
    assert client.aliases["previous_champion"] == "1"


def test_rejected_candidate_is_tagged_without_alias_change(tmp_path: Path):
    champion = _version("1", "run_champion")
    candidate = _version("2", "run_candidate")
    client = FakeClient(
        [champion, candidate],
        {"champion": "1", "candidate": "2"},
        {
            "run_champion": {
                "rows": 40.0,
                "sentiment_accuracy": 0.70,
                "theme_exact_match": 0.70,
            },
            "run_candidate": {
                "rows": 10.0,
                "sentiment_accuracy": 0.40,
                "theme_exact_match": 0.50,
            },
        },
    )

    result = promote_candidate(client, policy=POLICY, report_path=tmp_path / "promotion.json")

    assert result.status == "rejected"
    assert client.aliases["champion"] == "1"
    assert any(tag[2:] == ("promotion_status", "rejected") for tag in client.version_tags)


def test_promotion_reverts_alias_when_deployment_fails(tmp_path: Path, monkeypatch):
    champion = _version("1", "run_champion")
    candidate = _version("2", "run_candidate")
    client = FakeClient(
        [champion, candidate],
        {"champion": "1", "candidate": "2"},
        {
            "run_champion": {
                "rows": 40.0,
                "sentiment_accuracy": 0.60,
                "theme_exact_match": 0.70,
            },
            "run_candidate": {
                "rows": 40.0,
                "sentiment_accuracy": 0.61,
                "theme_exact_match": 0.71,
            },
        },
    )
    monkeypatch.setattr(
        "src.review_insights.model_registry.deploy_run_model_artifacts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("deploy failed")),
    )

    with pytest.raises(RuntimeError, match="deploy failed"):
        promote_candidate(
            client,
            policy=POLICY,
            report_path=tmp_path / "promotion.json",
            deploy_model_dir=tmp_path / "models",
        )

    assert client.aliases["champion"] == "1"
    assert any(tag[2:] == ("promotion_status", "deployment_failed") for tag in client.version_tags)


def test_rollback_swaps_champion_aliases(tmp_path: Path):
    champion = _version("2", "run_champion")
    previous = _version("1", "run_previous")
    client = FakeClient(
        [champion, previous],
        {"champion": "2", "previous_champion": "1"},
        {"run_champion": {}, "run_previous": {}},
    )

    result = rollback_champion(client, policy=POLICY, report_path=tmp_path / "rollback.json")

    assert result.status == "rolled_back"
    assert result.champion_version == "1"
    assert client.aliases["champion"] == "1"
    assert client.aliases["previous_champion"] == "2"


def test_deploy_run_model_artifacts_replaces_target_atomically(tmp_path: Path, monkeypatch):
    source = tmp_path / "download" / "model"
    source.mkdir(parents=True)
    for filename in ARTIFACT_FILENAMES:
        (source / filename).write_text("new", encoding="utf-8")

    class DownloadClient:
        def download_artifacts(self, _run_id, _path, _download_root):
            return str(source)

    monkeypatch.setattr(
        "src.review_insights.model_registry.load_project_model_artifacts",
        lambda *_args, **_kwargs: None,
    )
    target = tmp_path / "models"
    target.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")

    deployed = deploy_run_model_artifacts(DownloadClient(), "run_1", target)

    assert deployed == target.resolve()
    assert not (target / "old.txt").exists()
    assert (target / "manifest.json").read_text(encoding="utf-8") == "new"


def test_deploy_keeps_new_target_when_backup_cleanup_is_delayed(tmp_path: Path, monkeypatch):
    source = tmp_path / "download" / "model"
    source.mkdir(parents=True)
    for filename in ARTIFACT_FILENAMES:
        (source / filename).write_text("new", encoding="utf-8")

    class DownloadClient:
        def download_artifacts(self, _run_id, _path, _download_root):
            return str(source)

    monkeypatch.setattr(
        "src.review_insights.model_registry.load_project_model_artifacts",
        lambda *_args, **_kwargs: None,
    )
    original_rmtree = shutil.rmtree

    def delayed_backup_cleanup(path, *args, **kwargs):
        if ".models.backup-" in str(path):
            raise OSError("cleanup delayed")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(
        "src.review_insights.model_registry.shutil.rmtree",
        delayed_backup_cleanup,
    )
    target = tmp_path / "models"
    target.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")

    deployed = deploy_run_model_artifacts(DownloadClient(), "run_1", target)

    assert deployed == target.resolve()
    assert (target / "manifest.json").read_text(encoding="utf-8") == "new"


def test_rollback_requires_previous_champion(tmp_path: Path):
    champion = _version("2", "run_champion")
    client = FakeClient([champion], {"champion": "2"}, {"run_champion": {}})

    with pytest.raises(ValueError, match="previous_champion"):
        rollback_champion(client, policy=POLICY, report_path=tmp_path / "rollback.json")
