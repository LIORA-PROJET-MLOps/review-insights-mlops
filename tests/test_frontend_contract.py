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


def test_streamlit_frontend_exposes_visible_workspace_navigation():
    app = Path("src/review_insights/app.py").read_text(encoding="utf-8")

    assert 'WORKSPACES = ["Analyse", "Batch", "Dataset", "Monitoring", "Evaluation"]' in app
    assert "Espace de travail" in app
    assert "render_analysis_workspace" in app
    assert "render_monitoring_workspace" in app
    assert "render_header(workspace)" in app
    assert "st.tabs(" not in app


def test_streamlit_threshold_slider_accepts_the_default_value():
    app = Path("src/review_insights/app.py").read_text(encoding="utf-8")

    assert "DEFAULT_THEME_THRESHOLD,\n                0.01," in app


def test_frontends_share_the_review_insights_design_system():
    landing = Path("site/index.html").read_text(encoding="utf-8")
    application = Path("site/app-online.html").read_text(encoding="utf-8")
    design_system = Path("site/design-system.css").read_text(encoding="utf-8")

    assert 'href="./design-system.css"' in landing
    assert 'href="./design-system.css"' in application
    assert "--ri-accent: #ed8b59;" in design_system
    assert "@media (prefers-reduced-motion: reduce)" in design_system


def test_public_site_exposes_narrative_sections_and_interactive_filters():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/script.js").read_text(encoding="utf-8")

    for section_id in ("capabilities", "results", "architecture", "trajectory", "roadmap"):
        assert f'id="{section_id}"' in html
    assert 'data-result-filter="themes"' in html
    assert "aria-selected" in html
    assert "dataset.resultKind" in script


def test_online_app_exposes_progressive_operations_and_status_states():
    html = Path("site/app-online.html").read_text(encoding="utf-8")
    script = Path("site/app.js").read_text(encoding="utf-8")

    assert 'id="analyzeForm"' in html
    assert 'id="analyzeStatus"' in html
    assert 'id="connectionState"' in html
    assert html.count('<details class="ops-panel') == 3
    assert "event.preventDefault()" in script
    assert "button.disabled = true" in script
    assert "escapeHtml" in script
