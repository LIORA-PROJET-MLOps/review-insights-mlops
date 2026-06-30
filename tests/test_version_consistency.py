from pathlib import Path
import tomllib

from src.review_insights import __version__
from src.review_insights.settings import get_settings


def _env_value(path: str, name: str) -> str:
    prefix = f"{name}="
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{name} is missing from {path}")


def test_application_version_has_one_canonical_value(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == __version__
    assert get_settings().app_version == __version__
    assert _env_value(".env.example", "APP_VERSION") == __version__
    assert _env_value(".env.staging.example", "APP_VERSION") == __version__


def test_hugging_face_deployment_docs_use_current_version():
    for path in (
        "deploy/huggingface_api_space/README.md",
        "deploy/huggingface_api_space/SPACE_SETUP_FR.md",
    ):
        content = Path(path).read_text(encoding="utf-8")
        assert f"APP_VERSION={__version__}" in content
        assert "APP_VERSION=0.2.0" not in content
