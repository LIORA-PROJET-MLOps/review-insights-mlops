import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.review_insights.dataset import load_default_dataset, prepare_dataset
from src.review_insights.reporting import write_json_report, write_markdown_report
from src.review_insights.service import ReviewAnalysisService


def main() -> None:
    service = ReviewAnalysisService()
    df = prepare_dataset(load_default_dataset())
    report = service.evaluate_dataframe(df)
    reports_dir = ROOT_DIR / "reports"
    json_path = write_json_report(report, reports_dir / "default_evaluation.json")
    md_path = write_markdown_report(report, reports_dir / "default_evaluation.md")
    print(f"JSON report written to: {json_path}")
    print(f"Markdown report written to: {md_path}")


if __name__ == "__main__":
    main()
