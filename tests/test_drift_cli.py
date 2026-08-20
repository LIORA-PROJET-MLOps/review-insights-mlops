import subprocess
import sys


def test_evaluate_drift_cli_help_runs_from_project_root():
    completed = subprocess.run(
        [sys.executable, "pipelines/evaluate_drift.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "Evaluate production prediction" in completed.stdout
