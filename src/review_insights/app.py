from __future__ import annotations

from html import escape
from typing import Any, Dict

import pandas as pd
import streamlit as st

from .api_client import ReviewInsightsApiClient, ReviewInsightsClientError
from .config import APP_SUBTITLE, APP_TITLE, DEFAULT_THEME_THRESHOLD, MAX_SELECTABLE_ROWS, THEMES
from .dataset import flatten_results, load_default_dataset, prepare_dataset, safe_read_csv_filelike
from .engine import actionable_text


CLIENT = ReviewInsightsApiClient.from_env()

WORKSPACES = ["Analyse", "Batch", "Dataset", "Monitoring", "Evaluation"]
SENTIMENT_OPTIONS = ["Tous", "positive", "negative", "neutral", "unknown"]
THEME_FILTER_OPTIONS = ["Tous", "Livraison", "Service client", "Produit"]
THEME_LABELS = {theme.key: theme.label_fr for theme in THEMES}
THEME_KEYS_BY_LABEL = {theme.label_fr: theme.key for theme in THEMES}
SAMPLE_REVIEWS = {
    "Support lent": (
        "functional_support",
        "customer support never answered and the refund process was slow",
    ),
    "Livraison rapide": (
        "functional_delivery",
        "the parcel arrived early and the tracking updates were clear",
    ),
    "Produit fragile": (
        "functional_product",
        "the product broke after two days and the material feels cheap",
    ),
}


def configure_page() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ri-bg: #f6f7fb;
            --ri-surface: #ffffff;
            --ri-ink: #18212f;
            --ri-muted: #647084;
            --ri-border: #dbe1ea;
            --ri-blue: #275fe8;
            --ri-blue-soft: #e9efff;
            --ri-green: #0f766e;
            --ri-green-soft: #e3f7f3;
            --ri-red: #be123c;
            --ri-red-soft: #fde7ed;
            --ri-amber: #b45309;
            --ri-amber-soft: #fff2d7;
            --ri-purple: #6d28d9;
            --ri-purple-soft: #f0e8ff;
            --ri-shadow: 0 12px 30px rgba(24, 33, 47, 0.08);
        }
        .stApp {
            background: linear-gradient(180deg, #fafbfe 0%, var(--ri-bg) 100%);
            color: var(--ri-ink);
        }
        .block-container {
            max-width: 1360px;
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--ri-border);
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] label {
            color: var(--ri-muted);
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .ri-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
            gap: 16px;
            align-items: stretch;
            margin-bottom: 16px;
        }
        .ri-hero-main,
        .ri-panel,
        div[data-testid="stMetric"] {
            background: var(--ri-surface);
            border: 1px solid var(--ri-border);
            border-radius: 8px;
            box-shadow: var(--ri-shadow);
        }
        .ri-hero-main {
            padding: 22px;
            border-left: 5px solid var(--ri-blue);
        }
        .ri-overline {
            color: var(--ri-blue);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .ri-hero-main h1 {
            margin: 8px 0 8px;
            font-size: clamp(2rem, 4vw, 3.2rem);
            line-height: 1.02;
        }
        .ri-hero-main p {
            color: var(--ri-muted);
            max-width: 820px;
            margin: 0;
            line-height: 1.55;
        }
        .ri-hero-side {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }
        .ri-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0 16px;
        }
        .ri-kpi,
        .ri-theme-card,
        .ri-result-card {
            min-height: 112px;
            background: var(--ri-surface);
            border: 1px solid var(--ri-border);
            border-radius: 8px;
            padding: 14px;
            box-shadow: var(--ri-shadow);
        }
        .ri-kpi-label {
            color: var(--ri-muted);
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .ri-kpi-value {
            color: var(--ri-ink);
            font-size: 1.65rem;
            line-height: 1;
            font-weight: 850;
        }
        .ri-kpi-note {
            color: var(--ri-muted);
            font-size: 0.78rem;
            margin-top: 8px;
        }
        .ri-kpi-blue { border-top: 4px solid var(--ri-blue); }
        .ri-kpi-green { border-top: 4px solid var(--ri-green); }
        .ri-kpi-red { border-top: 4px solid var(--ri-red); }
        .ri-kpi-amber { border-top: 4px solid var(--ri-amber); }
        .ri-kpi-purple { border-top: 4px solid var(--ri-purple); }
        .ri-section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin: 4px 0 14px;
        }
        .ri-section-title h2 {
            margin: 0;
            font-size: 1.35rem;
        }
        .ri-section-title p {
            margin: 4px 0 0;
            color: var(--ri-muted);
        }
        .ri-panel {
            padding: 16px;
            margin-bottom: 16px;
        }
        .ri-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .ri-badge {
            display: inline-flex;
            align-items: center;
            min-height: 30px;
            border-radius: 999px;
            padding: 0 10px;
            font-size: 0.82rem;
            font-weight: 800;
            border: 1px solid transparent;
        }
        .ri-badge-positive {
            color: var(--ri-green);
            background: var(--ri-green-soft);
            border-color: rgba(15, 118, 110, 0.18);
        }
        .ri-badge-negative {
            color: var(--ri-red);
            background: var(--ri-red-soft);
            border-color: rgba(190, 18, 60, 0.18);
        }
        .ri-badge-neutral,
        .ri-badge-off {
            color: #475569;
            background: #eef2f7;
            border-color: rgba(100, 112, 132, 0.18);
        }
        .ri-badge-theme {
            color: var(--ri-blue);
            background: var(--ri-blue-soft);
            border-color: rgba(39, 95, 232, 0.18);
        }
        .ri-badge-warning {
            color: var(--ri-amber);
            background: var(--ri-amber-soft);
            border-color: rgba(180, 83, 9, 0.18);
        }
        .ri-theme-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin: 14px 0;
        }
        .ri-theme-card {
            display: flex;
            flex-direction: column;
            gap: 10px;
            min-height: 245px;
        }
        .ri-theme-card h3 {
            margin: 0;
            font-size: 1.05rem;
        }
        .ri-theme-card p {
            margin: 0;
            color: var(--ri-muted);
            line-height: 1.45;
        }
        .ri-theme-positive { border-left: 5px solid var(--ri-green); }
        .ri-theme-negative { border-left: 5px solid var(--ri-red); }
        .ri-theme-neutral { border-left: 5px solid var(--ri-amber); }
        .ri-theme-off { border-left: 5px solid #cbd5e1; }
        .ri-confidence {
            width: 100%;
            height: 8px;
            border-radius: 999px;
            background: #e9eef6;
            overflow: hidden;
        }
        .ri-confidence span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--ri-blue), var(--ri-green));
        }
        .ri-result-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 12px;
        }
        .ri-result-card {
            min-height: 100px;
        }
        .ri-result-card strong {
            display: block;
            font-size: 1.35rem;
            color: var(--ri-ink);
            margin-top: 6px;
        }
        .ri-result-card span {
            color: var(--ri-muted);
            font-size: 0.82rem;
            font-weight: 700;
        }
        div[data-testid="stMetric"] {
            padding: 0.8rem 0.9rem;
        }
        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button {
            border-radius: 8px;
            min-height: 2.7rem;
            font-weight: 800;
        }
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"] {
            background: var(--ri-blue);
            border-color: var(--ri-blue);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--ri-border);
            border-radius: 8px;
            overflow: hidden;
        }
        div[data-testid="stExpander"] {
            border-radius: 8px;
            border-color: var(--ri-border);
        }
        @media (max-width: 1100px) {
            .ri-hero,
            .ri-theme-grid,
            .ri-result-grid {
                grid-template-columns: 1fr;
            }
            .ri-kpi-grid,
            .ri-hero-side {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 720px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .ri-kpi-grid,
            .ri-hero-side {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _display_text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def _confidence_width(value: Any) -> int:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0
    if confidence <= 1:
        confidence *= 100
    return int(min(max(confidence, 0), 100))


def _kpi_card(label: str, value: Any, tone: str = "blue", note: str | None = None) -> str:
    note_html = f'<div class="ri-kpi-note">{escape(note)}</div>' if note else ""
    return (
        f'<div class="ri-kpi ri-kpi-{escape(tone)}">'
        f'<div class="ri-kpi-label">{escape(label)}</div>'
        f'<div class="ri-kpi-value">{escape(_display_text(value))}</div>'
        f"{note_html}"
        "</div>"
    )


def render_kpi_grid(items: list[tuple[str, Any, str, str | None]]) -> None:
    cards = "".join(_kpi_card(label, value, tone, note) for label, value, tone, note in items)
    st.markdown(f'<div class="ri-kpi-grid">{cards}</div>', unsafe_allow_html=True)


def sentiment_badge(sentiment: str | None) -> str:
    normalized = sentiment or "unknown"
    label = {
        "positive": "Positif",
        "negative": "Negatif",
        "neutral": "Neutre",
        "unknown": "Inconnu",
    }.get(normalized, normalized)
    css = {
        "positive": "ri-badge-positive",
        "negative": "ri-badge-negative",
        "neutral": "ri-badge-neutral",
    }.get(normalized, "ri-badge-off")
    return f'<span class="ri-badge {css}">{escape(label)}</span>'


def theme_badge(label: str) -> str:
    return f'<span class="ri-badge ri-badge-theme">{escape(label)}</span>'


def render_section_title(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        (
            '<div class="ri-section-title"><div>'
            f"<h2>{escape(title)}</h2>{subtitle_html}"
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )


def render_header(df: pd.DataFrame) -> None:
    negative = int((df["sentiment_label"] == "negative").sum())
    positive = int((df["sentiment_label"] == "positive").sum())
    neutral = int((df["sentiment_label"] == "neutral").sum())
    side_cards = "".join(
        [
            _kpi_card("Dataset", len(df), "blue", "reviews chargees"),
            _kpi_card("Negatives", negative, "red", "labels reference"),
            _kpi_card("Positives", positive, "green", "labels reference"),
            _kpi_card("Neutres", neutral, "amber", "labels reference"),
        ]
    )
    st.markdown(
        (
            '<div class="ri-hero"><div class="ri-hero-main">'
            '<div class="ri-overline">Console POC</div>'
            f"<h1>{escape(APP_TITLE)}</h1><p>{escape(APP_SUBTITLE)}</p>"
            '<div class="ri-badge-row">'
            f'{theme_badge("Livraison")}{theme_badge("Service client")}'
            f'{theme_badge("Produit")}'
            '<span class="ri-badge ri-badge-warning">Human review</span>'
            '</div></div><div class="ri-hero-side">'
            f"{side_cards}</div></div>"
        ),
        unsafe_allow_html=True,
    )


def filter_dataset(df: pd.DataFrame, query: str, sentiment_filter: str, theme_filter: str) -> pd.DataFrame:
    filtered = df.copy()
    if query.strip():
        q = query.strip().lower()
        mask = (
            filtered["review_id"].astype(str).str.lower().str.contains(q, regex=False)
            | filtered["review_title"].astype(str).str.lower().str.contains(q, regex=False)
            | filtered["review_body"].astype(str).str.lower().str.contains(q, regex=False)
        )
        filtered = filtered[mask]

    if sentiment_filter != "Tous":
        filtered = filtered[filtered["sentiment_label"] == sentiment_filter]

    theme_map = {
        "Tous": None,
        "Livraison": "theme_livraison",
        "Service client": "theme_sav",
        "Produit": "theme_produit",
    }
    selected_col = theme_map[theme_filter]
    if selected_col:
        filtered = filtered[filtered[selected_col] == 1]
    return filtered.reset_index(drop=True)


def analyze_dataframe(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        analysis = CLIENT.analyze(
            review_text=f"{row['review_title']} {row['review_body']}".strip(),
            review_id=str(row["review_id"]),
            threshold=threshold,
        )
        record = dict(row)
        for theme in ("livraison", "sav", "produit"):
            column = f"theme_{theme}"
            if column in record:
                record[f"true_{column}"] = record[column]
        record.update(analysis)
        rows.append(record)
    return pd.DataFrame(rows)


def render_result_cards(result: Dict[str, Any]) -> None:
    detected_themes = result.get("themes_detected", [])
    theme_labels = [THEME_LABELS.get(key, key) for key in detected_themes]
    theme_html = "".join(theme_badge(label) for label in theme_labels) or theme_badge("Autre")
    human_review = "Oui" if result.get("needs_human_review") else "Non"
    human_badge = "ri-badge-warning" if result.get("needs_human_review") else "ri-badge-positive"

    st.markdown(
        (
            '<div class="ri-result-grid">'
            '<div class="ri-result-card"><span>Sentiment global</span>'
            f'<strong>{sentiment_badge(result.get("global_sentiment"))}</strong></div>'
            '<div class="ri-result-card"><span>Themes detectes</span>'
            f'<div class="ri-badge-row">{theme_html}</div></div>'
            '<div class="ri-result-card"><span>Score global</span>'
            f'<strong>{escape(_display_text(result.get("score_global")))}</strong></div>'
            '<div class="ri-result-card"><span>Revue humaine</span>'
            f'<div class="ri-badge-row"><span class="ri-badge {human_badge}">'
            f"{human_review}</span></div></div></div>"
        ),
        unsafe_allow_html=True,
    )


def render_operational_reading(result: Dict[str, Any]) -> None:
    positives = ", ".join(result.get("positive_terms", [])) or "Aucun"
    negatives = ", ".join(result.get("negative_terms", [])) or "Aucun"
    if result.get("needs_human_review"):
        st.warning("Cas ambigu: revue humaine recommandee.")
    else:
        st.success("Signal exploitable pour une lecture operationnelle rapide.")
    st.markdown(
        (
            '<div class="ri-badge-row">'
            f'<span class="ri-badge ri-badge-positive">Positifs: {escape(positives)}</span>'
            f'<span class="ri-badge ri-badge-negative">Negatifs: {escape(negatives)}</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_theme_cards(result: Dict[str, Any]) -> None:
    cards = []
    for theme in THEMES:
        present = result.get(f"theme_{theme.key}", 0) == 1
        sentiment = result.get(f"sent_{theme.key}") if present else None
        confidence = result.get(f"conf_{theme.key}", 0)
        evidence = result.get(f"evidence_{theme.key}", [])
        css = "ri-theme-off"
        if present and sentiment == "positive":
            css = "ri-theme-positive"
        elif present and sentiment == "negative":
            css = "ri-theme-negative"
        elif present:
            css = "ri-theme-neutral"

        status = "Detecte" if present else "Non detecte"
        sentiment_html = sentiment_badge(sentiment) if present else sentiment_badge("unknown")
        evidence_html = "".join(theme_badge(str(item)) for item in evidence[:4])
        if not evidence_html:
            evidence_html = '<span class="ri-badge ri-badge-off">Aucun signal fort</span>'
        action_text = (
            actionable_text(theme.key, result.get(f"sent_{theme.key}"))
            if present
            else "Pas de signal exploitable sur ce theme."
        )
        width = _confidence_width(confidence)
        cards.append(
            (
                f'<div class="ri-theme-card {css}"><h3>{escape(theme.label_fr)}</h3>'
                '<div class="ri-badge-row">'
                f'<span class="ri-badge ri-badge-theme">{status}</span>{sentiment_html}'
                "</div><div>"
                f"<p>Confiance: {escape(_display_text(confidence))}</p>"
                f'<div class="ri-confidence"><span style="width:{width}%"></span></div>'
                f'</div><div class="ri-badge-row">{evidence_html}</div>'
                f"<p>{escape(action_text)}</p></div>"
            )
        )
    st.markdown(f'<div class="ri-theme-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_feedback_form(result: Dict[str, Any]) -> None:
    with st.container(border=True):
        render_section_title("Correction humaine")
        with st.form("feedback_form", clear_on_submit=False):
            c1, c2, c3 = st.columns([1.1, 1.1, 0.9])
            with c1:
                theme_label = st.selectbox("Theme corrige", [theme.label_fr for theme in THEMES])
                theme_key = THEME_KEYS_BY_LABEL[theme_label]
            with c2:
                current_sentiment = result.get(f"sent_{theme_key}") or "neutral"
                if current_sentiment not in {"negative", "neutral", "positive"}:
                    current_sentiment = "neutral"
                corrected_sentiment = st.selectbox(
                    "Sentiment corrige",
                    ["negative", "neutral", "positive"],
                    index=["negative", "neutral", "positive"].index(current_sentiment),
                )
            with c3:
                corrected_theme_present = st.checkbox(
                    "Theme present",
                    value=bool(result.get(f"theme_{theme_key}", 0)),
                )
            reviewer = st.text_input("Annotateur", value="demo_user")
            notes = st.text_area("Notes", value="", height=90)
            submitted = st.form_submit_button("Enregistrer la correction", type="primary")
            if submitted:
                try:
                    feedback = CLIENT.submit_feedback(
                        {
                            "review_id": result["review_id"],
                            "theme": theme_key,
                            "corrected_theme_present": int(corrected_theme_present),
                            "corrected_sentiment": corrected_sentiment,
                            "reviewer": reviewer,
                            "notes": notes,
                            "source": "streamlit",
                        }
                    )
                    st.success(f"Correction enregistree: {feedback.get('status', 'ok')}")
                except ReviewInsightsClientError as exc:
                    st.error(str(exc))


def render_dataset_filters(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3 = st.columns([1.4, 0.85, 0.85])
    with c1:
        query = st.text_input("Recherche", value="", placeholder="ID, titre ou texte")
    with c2:
        sentiment_filter = st.radio("Sentiment", SENTIMENT_OPTIONS, horizontal=True)
    with c3:
        theme_filter = st.radio("Theme", THEME_FILTER_OPTIONS, horizontal=True)
    filtered_df = filter_dataset(df, query, sentiment_filter, theme_filter)
    render_kpi_grid(
        [
            ("Resultats", len(filtered_df), "blue", "apres filtres"),
            ("Livraison", int(filtered_df["theme_livraison"].sum()), "purple", None),
            ("SAV", int(filtered_df["theme_sav"].sum()), "amber", None),
            ("Produit", int(filtered_df["theme_produit"].sum()), "green", None),
        ]
    )
    return filtered_df


def render_analysis_workspace(df: pd.DataFrame, threshold: float) -> None:
    render_section_title("Analyse instantanee", "Selection, saisie et resultat sur le meme ecran.")
    with st.container(border=True):
        filtered_df = render_dataset_filters(df)
        table_cols = ["review_id", "review_title", "review_body", "sentiment_label"]
        st.dataframe(
            filtered_df[table_cols].head(MAX_SELECTABLE_ROWS),
            height=250,
            use_container_width=True,
        )

    selection_options = ["Saisie manuelle"]
    lookup = {}
    for _, row in filtered_df.head(MAX_SELECTABLE_ROWS).iterrows():
        preview = str(row["review_body"])[:110].replace("\n", " ")
        label = f"{row['review_id']} - {preview}"
        selection_options.append(label)
        lookup[label] = row.to_dict()

    left, right = st.columns([0.95, 1.05])
    selected_text = ""
    selected_id = "manual_review"
    ground_truth = None

    with left:
        with st.container(border=True):
            render_section_title("Review a analyser")
            sample_choice = st.selectbox("Exemple rapide", ["Aucun", *SAMPLE_REVIEWS.keys()])
            selected = st.selectbox("Review du dataset", selection_options)
            if sample_choice != "Aucun":
                selected_id, selected_text = SAMPLE_REVIEWS[sample_choice]
            elif selected != "Saisie manuelle":
                row = lookup[selected]
                selected_text = f"{row['review_title']} {row['review_body']}".strip()
                selected_id = str(row["review_id"])
                ground_truth = row

            review_id = st.text_input("Review ID", value=selected_id)
            review_text = st.text_area(
                "Texte de la review",
                value=selected_text,
                height=210,
                placeholder="Type an English customer review here.",
            )
            analyze_clicked = st.button(
                "Analyser",
                type="primary",
                use_container_width=True,
            )
            if analyze_clicked:
                if not review_text.strip():
                    st.warning("Le texte de la review est obligatoire.")
                else:
                    try:
                        st.session_state["instant_result"] = CLIENT.analyze(
                            review_text=review_text,
                            review_id=review_id,
                            threshold=threshold,
                        )
                    except ReviewInsightsClientError as exc:
                        st.error(str(exc))

    result = st.session_state.get("instant_result")
    with right:
        with st.container(border=True):
            render_section_title("Resultat")
            if result:
                render_result_cards(result)
                render_operational_reading(result)
            else:
                st.info("Aucun resultat pour le moment.")

    if result:
        render_section_title("Details par theme")
        render_theme_cards(result)
        render_feedback_form(result)
        with st.expander("JSON de sortie"):
            st.json(result)

    if ground_truth:
        with st.container(border=True):
            render_section_title("Verite terrain")
            render_kpi_grid(
                [
                    ("Sentiment", ground_truth["sentiment_label"], "blue", None),
                    ("Livraison", int(ground_truth["theme_livraison"]), "purple", None),
                    ("SAV", int(ground_truth["theme_sav"]), "amber", None),
                    ("Produit", int(ground_truth["theme_produit"]), "green", None),
                ]
            )


def render_batch_workspace(df: pd.DataFrame, threshold: float) -> None:
    render_section_title("Batch", "Re-analyse et export du dataset charge.")
    with st.container(border=True):
        render_kpi_grid(
            [
                ("Lignes", len(df), "blue", "dataset actif"),
                ("Seuil", threshold, "amber", "themes"),
                ("Colonnes", len(df.columns), "purple", "schema"),
                ("Max preview", MAX_SELECTABLE_ROWS, "green", None),
            ]
        )
        st.dataframe(df.head(MAX_SELECTABLE_ROWS), height=320, use_container_width=True)
        if st.button("Lancer la re-analyse du dataset", type="primary", use_container_width=True):
            try:
                st.session_state["batch_enriched"] = analyze_dataframe(df, threshold)
            except ReviewInsightsClientError as exc:
                st.error(str(exc))

    enriched = st.session_state.get("batch_enriched")
    if enriched is not None:
        with st.container(border=True):
            render_section_title("Resultats batch")
            export_df = flatten_results(enriched)
            st.dataframe(export_df, height=520, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.download_button(
                "Telecharger le CSV enrichi",
                data=export_df.to_csv(index=False).encode("utf-8"),
                file_name="review_insights_poc.csv",
                mime="text/csv",
                use_container_width=True,
            )
            c2.download_button(
                "Telecharger le JSON enrichi",
                data=enriched.to_json(orient="records", force_ascii=False, indent=2),
                file_name="review_insights_poc.json",
                mime="application/json",
                use_container_width=True,
            )


def render_dataset_workspace(df: pd.DataFrame) -> None:
    render_section_title("Dataset", "Exploration rapide des donnees chargees.")
    with st.container(border=True):
        filtered_df = render_dataset_filters(df)
        st.dataframe(filtered_df, height=620, use_container_width=True)


def render_dashboard(df: pd.DataFrame) -> None:
    with st.container(border=True):
        render_section_title("Distribution labels")
        c1, c2 = st.columns(2)
        with c1:
            theme_counts = pd.DataFrame(
                {
                    "theme": ["Livraison", "Service client", "Produit"],
                    "count": [
                        int(df["theme_livraison"].sum()),
                        int(df["theme_sav"].sum()),
                        int(df["theme_produit"].sum()),
                    ],
                }
            ).set_index("theme")
            st.bar_chart(theme_counts)
        with c2:
            st.bar_chart(df["sentiment_label"].value_counts())


def render_monitoring_workspace(df: pd.DataFrame) -> None:
    render_section_title("Monitoring", "Sante runtime et metriques API.")
    render_kpi_grid(
        [
            ("Rows dataset", len(df), "blue", None),
            ("Negative", int((df["sentiment_label"] == "negative").sum()), "red", None),
            ("Positive", int((df["sentiment_label"] == "positive").sum()), "green", None),
            ("Neutral", int((df["sentiment_label"] == "neutral").sum()), "amber", None),
        ]
    )
    render_dashboard(df)

    with st.container(border=True):
        render_section_title("Backend")
        try:
            health = CLIENT.health()
            metrics = CLIENT.metrics()
            render_kpi_grid(
                [
                    ("Backend", health.get("inference_backend", "unknown"), "blue", None),
                    ("Requetes", metrics.get("total_requests", 0), "green", None),
                    (
                        "Human review",
                        _format_percent(metrics.get("human_review_rate", 0.0)),
                        "amber",
                        None,
                    ),
                    ("HTTP", metrics.get("http_requests_total", 0), "purple", None),
                ]
            )
            with st.expander("Healthcheck"):
                st.json(health)
            with st.expander("Metriques runtime"):
                st.json(metrics)
        except ReviewInsightsClientError as exc:
            st.error(str(exc))

    with st.container(border=True):
        render_section_title("Feedback recent")
        try:
            feedback = CLIENT.recent_feedback(limit=20)
            records = feedback.get("records", [])
            if records:
                st.dataframe(pd.DataFrame(records), height=260, use_container_width=True)
            else:
                st.info("Aucune correction humaine enregistree.")
        except ReviewInsightsClientError as exc:
            st.warning(str(exc))


def render_evaluation_workspace() -> None:
    render_section_title("Evaluation", "Benchmark offline du dataset de reference.")
    with st.container(border=True):
        if st.button("Lancer l'evaluation de reference", type="primary", use_container_width=True):
            try:
                st.session_state["default_evaluation"] = CLIENT.evaluate_default()
            except ReviewInsightsClientError as exc:
                st.error(str(exc))

        evaluation = st.session_state.get("default_evaluation")
        if evaluation:
            summary = evaluation.get("summary", {})
            render_kpi_grid(
                [
                    (
                        "Sentiment accuracy",
                        _format_percent(summary.get("sentiment_accuracy", 0.0)),
                        "blue",
                        None,
                    ),
                    (
                        "Sentiment F1",
                        _format_percent(summary.get("sentiment_macro_f1", 0.0)),
                        "green",
                        None,
                    ),
                    (
                        "Theme exact",
                        _format_percent(summary.get("theme_exact_match", 0.0)),
                        "purple",
                        None,
                    ),
                    (
                        "Theme F1",
                        _format_percent(summary.get("theme_f1_macro", 0.0)),
                        "amber",
                        None,
                    ),
                ]
            )
            with st.expander("Details evaluation"):
                st.json(summary)
        else:
            st.info("Evaluation non lancee.")


def load_active_dataset(uploaded_file: Any | None) -> pd.DataFrame:
    if uploaded_file is not None:
        raw_df = safe_read_csv_filelike(uploaded_file)
    else:
        try:
            dataset_payload = CLIENT.default_dataset()
            raw_df = pd.DataFrame(dataset_payload.get("records", []))
        except ReviewInsightsClientError as exc:
            st.sidebar.warning(f"Service data indisponible, dataset local utilise: {exc}")
            raw_df = load_default_dataset()
    return prepare_dataset(raw_df)


def main() -> None:
    configure_page()
    inject_styles()

    with st.sidebar:
        st.markdown("## Review Insights+")
        workspace = st.radio("Espace de travail", WORKSPACES, index=0)
        st.markdown("---")
        uploaded_file = st.file_uploader("Dataset CSV", type=["csv"])
        threshold = st.slider(
            "Seuil themes",
            0.15,
            0.85,
            DEFAULT_THEME_THRESHOLD,
            0.05,
        )
        st.markdown("---")
        st.caption("API, data, monitoring et feedback sont accessibles depuis les ecrans dedies.")

    df = load_active_dataset(uploaded_file)
    render_header(df)

    if workspace == "Analyse":
        render_analysis_workspace(df, threshold)
    elif workspace == "Batch":
        render_batch_workspace(df, threshold)
    elif workspace == "Dataset":
        render_dataset_workspace(df)
    elif workspace == "Monitoring":
        render_monitoring_workspace(df)
    elif workspace == "Evaluation":
        render_evaluation_workspace()
