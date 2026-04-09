from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from .config import APP_SUBTITLE, APP_TITLE, DEFAULT_THEME_THRESHOLD, MAX_SELECTABLE_ROWS, THEMES
from .dataset import flatten_results, load_default_dataset, prepare_dataset, safe_read_csv_filelike
from .engine import actionable_text
from .service import get_review_analysis_service


SERVICE = get_review_analysis_service()


def configure_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="💬", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(0, 182, 122, 0.14), transparent 32%),
                linear-gradient(180deg, #f4f8fb 0%, #ebf1f6 100%);
            color: #102033;
        }
        .block-container {
            max-width: 1440px;
            padding-top: 1rem;
            padding-bottom: 2rem;
        }
        .hero {
            background: linear-gradient(135deg, #12324a 0%, #1f4d68 60%, #00b67a 100%);
            color: white;
            border-radius: 24px;
            padding: 1.6rem 1.8rem;
                box-shadow: 0 18px 44px rgba(18, 50, 74, 0.18);
            margin-bottom: 1rem;
        }
        .hero h1 { margin: 0; font-size: 2.3rem; }
        .hero p { margin-top: 0.55rem; color: rgba(255,255,255,0.9); max-width: 900px; }
        .card {
            background: rgba(255,255,255,0.96);
            border: 1px solid rgba(16, 32, 51, 0.06);
            border-radius: 20px;
            padding: 1rem;
            box-shadow: 0 10px 24px rgba(16, 32, 51, 0.05);
            margin-bottom: 1rem;
        }
        .theme-card {
            background: white;
            border-radius: 18px;
            padding: 1rem;
            min-height: 220px;
            border: 1px solid rgba(16, 32, 51, 0.06);
            box-shadow: 0 8px 20px rgba(16, 32, 51, 0.05);
        }
        .theme-positive { border-left: 6px solid #16a34a; }
        .theme-negative { border-left: 6px solid #dc2626; }
        .theme-neutral { border-left: 6px solid #64748b; }
        .theme-off { border-left: 6px solid #d7dde6; opacity: 0.88; }
        .badge {
            display: inline-block;
            padding: 0.34rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }
        .badge-positive { background: #dcfce7; color: #166534; }
        .badge-negative { background: #fee2e2; color: #991b1b; }
        .badge-neutral { background: #e2e8f0; color: #334155; }
        .badge-theme { background: #dbeafe; color: #1d4ed8; }
        .section-title { font-size: 1.05rem; font-weight: 800; margin-bottom: 0.65rem; }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid rgba(16, 32, 51, 0.06);
            border-radius: 18px;
            padding: 0.7rem 0.85rem;
            box-shadow: 0 8px 18px rgba(16, 32, 51, 0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sentiment_badge(sentiment: str) -> str:
    mapping = {
        "positive": '<span class="badge badge-positive">Positive</span>',
        "negative": '<span class="badge badge-negative">Negative</span>',
        "neutral": '<span class="badge badge-neutral">Neutral</span>',
        "unknown": '<span class="badge badge-neutral">Unknown</span>',
    }
    return mapping.get(sentiment, mapping["unknown"])


def theme_badge(label: str) -> str:
    return f'<span class="badge badge-theme">{label}</span>'


def render_header(df: pd.DataFrame) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div style="font-size:0.82rem; letter-spacing:0.14em; text-transform:uppercase; opacity:0.78; font-weight:700;">
                Projet Trustpilot - POC MVP final
            </div>
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUBTITLE} Le produit et la documentation sont cadres en francais, mais l'analyse est volontairement optimisee pour des commentaires en anglais, conformement aux donnees et modeles du projet.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    cols[0].metric("Lignes du dataset", len(df))
    cols[1].metric("Mentions livraison", int(df["theme_livraison"].sum()))
    cols[2].metric("Mentions SAV", int(df["theme_sav"].sum()))
    cols[3].metric("Mentions produit", int(df["theme_produit"].sum()))


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
        analysis = analyze_review(
            f"{row['review_title']} {row['review_body']}".strip(),
            review_id=str(row["review_id"]),
            threshold=threshold,
        )
        record = dict(row)
        record.update(analysis)
        rows.append(record)
    return pd.DataFrame(rows)


def render_summary(result: Dict) -> None:
    theme_html = "".join(
        theme_badge(next(theme.label_fr for theme in THEMES if theme.key == key))
        for key in result["themes_detected"]
    ) if result["themes_detected"] else theme_badge("Autre")
    st.markdown(
        f"""
            <div class="card">
            <div class="section-title">Resultat instantane</div>
            <div style="margin-bottom:0.45rem;">{sentiment_badge(result['global_sentiment'])}{theme_html}</div>
            <div>Score global: <b>{result['score_global']}</b></div>
            <div>Revue humaine necessaire: <b>{'Oui' if result['needs_human_review'] else 'Non'}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_theme_cards(result: Dict) -> None:
    cols = st.columns(3)
    for idx, theme in enumerate(THEMES):
        present = result.get(f"theme_{theme.key}", 0) == 1
        sentiment = result.get(f"sent_{theme.key}") or "not detected"
        confidence = result.get(f"conf_{theme.key}", 0)
        evidence = result.get(f"evidence_{theme.key}", [])
        css = "theme-off"
        if present and sentiment == "positive":
            css = "theme-positive"
        elif present and sentiment == "negative":
            css = "theme-negative"
        elif present:
            css = "theme-neutral"
        evidence_text = ", ".join(evidence) if evidence else "Aucun signal lexical fort"
        action_text = actionable_text(theme.key, result.get(f"sent_{theme.key}")) if present else "Pas de signal exploitable sur ce theme."
        cols[idx].markdown(
            f"""
            <div class="theme-card {css}">
                <div style="font-size:1.08rem; font-weight:800;">{theme.icon} {theme.label_fr}</div>
                <div style="margin-top:0.45rem;"><b>Detecte:</b> {'Oui' if present else 'Non'}</div>
                <div><b>Sentiment:</b> {sentiment}</div>
                <div><b>Confiance:</b> {confidence}</div>
                <div style="margin-top:0.5rem;"><b>Evidence:</b> {evidence_text}</div>
                <div style="margin-top:0.65rem; color:#475569;">{action_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard(df: pd.DataFrame) -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Dashboard de cadrage</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(
            pd.DataFrame(
                {
                    "theme": ["Livraison", "Service client", "Produit"],
                    "count": [
                        int(df["theme_livraison"].sum()),
                        int(df["theme_sav"].sum()),
                        int(df["theme_produit"].sum()),
                    ],
                }
            ).set_index("theme")
        )
    with c2:
        st.bar_chart(df["sentiment_label"].value_counts())
    st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    configure_page()
    inject_styles()

    with st.sidebar:
        st.markdown("## Source de donnees")
        uploaded_file = st.file_uploader("Importer un CSV", type=["csv"])
        threshold = st.slider("Seuil de detection des themes", 0.15, 0.85, DEFAULT_THEME_THRESHOLD, 0.05)
        st.markdown("## Notes produit")
        st.caption("Documentation en francais. Analyse courante optimisee pour les commentaires en anglais.")

    raw_df = safe_read_csv_filelike(uploaded_file) if uploaded_file is not None else load_default_dataset()
    df = prepare_dataset(raw_df)

    render_header(df)
    tab1, tab2, tab3 = st.tabs(["Analyse instantanee", "Jeu de donnees complet", "Dashboard POC"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Analyser un commentaire</div>', unsafe_allow_html=True)
        f1, f2, f3 = st.columns([1.2, 0.8, 0.8])
        with f1:
            query = st.text_input("Recherche libre", value="")
        with f2:
            sentiment_filter = st.selectbox("Filtre sentiment label", ["Tous", "positive", "negative", "neutral", "unknown"])
        with f3:
            theme_filter = st.selectbox("Filtre theme label", ["Tous", "Livraison", "Service client", "Produit"])

        filtered_df = filter_dataset(df, query, sentiment_filter, theme_filter)
        st.caption(f"{len(filtered_df)} ligne(s) disponible(s) pour analyse.")
        st.dataframe(filtered_df[["review_id", "review_title", "review_body", "sentiment_label"]].head(MAX_SELECTABLE_ROWS), use_container_width=True, height=280)

        selection_options = ["Saisie manuelle"]
        lookup = {}
        for _, row in filtered_df.head(MAX_SELECTABLE_ROWS).iterrows():
            preview = str(row["review_body"])[:120].replace("\n", " ")
            label = f"{row['review_id']} - {preview}"
            selection_options.append(label)
            lookup[label] = row.to_dict()

        selected = st.selectbox("Choisir une review", selection_options)
        selected_text = ""
        selected_id = "manual_review"
        ground_truth = None
        if selected != "Saisie manuelle":
            row = lookup[selected]
            selected_text = f"{row['review_title']} {row['review_body']}".strip()
            selected_id = str(row["review_id"])
            ground_truth = row

        left, right = st.columns([1, 1])
        with left:
            review_text = st.text_area("Texte de la review", value=selected_text, height=220, placeholder="Type an English customer review here.")
            review_id = st.text_input("Review ID", value=selected_id)
        with right:
            result = SERVICE.analyze(review_text=review_text, review_id=review_id, threshold=threshold).model_dump()
            render_summary(result)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Lecture operationnelle</div>', unsafe_allow_html=True)
            if result["needs_human_review"]:
                st.warning("Cas borderline ou ambigu: une revue humaine est recommandee.")
            else:
                st.success("Signal suffisamment clair pour une lecture operationnelle rapide.")
            st.write(f"Indices positifs: {', '.join(result['positive_terms']) if result['positive_terms'] else 'Aucun'}")
            st.write(f"Indices negatifs: {', '.join(result['negative_terms']) if result['negative_terms'] else 'Aucun'}")
            st.markdown('</div>', unsafe_allow_html=True)

        render_theme_cards(result)

        if ground_truth:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Verite terrain du dataset</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            cols[0].metric("Sentiment label", ground_truth["sentiment_label"])
            cols[1].metric("Livraison", int(ground_truth["theme_livraison"]))
            cols[2].metric("SAV", int(ground_truth["theme_sav"]))
            cols[3].metric("Produit", int(ground_truth["theme_produit"]))
            st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("Afficher le JSON de sortie"):
            st.json(result)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Dataset complet</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, height=620)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Batch re-analysis</div>', unsafe_allow_html=True)
        enriched = SERVICE.analyze_dataframe(df, threshold)
        export_df = flatten_results(enriched)
        st.dataframe(export_df, use_container_width=True, height=520)
        c1, c2 = st.columns(2)
        c1.download_button("Telecharger le CSV enrichi", data=export_df.to_csv(index=False).encode("utf-8"), file_name="review_insights_poc.csv", mime="text/csv", use_container_width=True)
        c2.download_button("Telecharger le JSON enrichi", data=enriched.to_json(orient="records", force_ascii=False, indent=2), file_name="review_insights_poc.json", mime="application/json", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        cols = st.columns(4)
        cols[0].metric("Rows dataset", len(df))
        cols[1].metric("Negative labels", int((df["sentiment_label"] == "negative").sum()))
        cols[2].metric("Positive labels", int((df["sentiment_label"] == "positive").sum()))
        cols[3].metric("Neutral labels", int((df["sentiment_label"] == "neutral").sum()))
        render_dashboard(df)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Backend et monitoring</div>', unsafe_allow_html=True)
        metrics = SERVICE.get_monitoring_metrics()
        m1, m2, m3 = st.columns(3)
        m1.metric("Backend actif", SERVICE.backend_name)
        m2.metric("Requetes analysees", metrics["total_requests"])
        m3.metric("Taux human review", metrics["human_review_rate"])
        st.json(metrics)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Evaluation offline</div>', unsafe_allow_html=True)
        evaluation = SERVICE.evaluate_dataframe(df)
        st.json(evaluation["summary"])
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Cadrage MVP</div>', unsafe_allow_html=True)
        st.markdown(
            """
            - Entree: commentaires clients en anglais.
            - Sortie: detection des themes `Livraison`, `Service client`, `Produit`, sentiment global et par theme, score de confiance et drapeau `human review`.
            - Usage: demonstration POC/MVP, lecture operationnelle rapide, exports CSV/JSON.
            - Capacites MLOps visibles: healthcheck, metrics runtime, evaluation offline, manifest d'artefacts.
            """
        )
        st.markdown('</div>', unsafe_allow_html=True)
