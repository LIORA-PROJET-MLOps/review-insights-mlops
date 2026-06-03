from pathlib import Path


def test_static_frontend_reads_evaluation_summary_contract():
    script = Path("site/app.js").read_text(encoding="utf-8")

    assert "const summary = payload.summary || {};" in script
    assert "summary.sentiment_accuracy" in script
    assert "payload.sentiment_accuracy" not in script


def test_public_frontend_does_not_collect_api_secrets():
    html = Path("site/app-online.html").read_text(encoding="utf-8")
    script = Path("site/app.js").read_text(encoding="utf-8")

    assert 'id="apiKey"' not in html
    assert "X-API-Key" not in script
