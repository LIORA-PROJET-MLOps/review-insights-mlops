from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .config import DEFAULT_THEME_THRESHOLD


THEME_KEYWORDS = {
    "livraison": {
        "strong": [
            "delivery",
            "shipping",
            "shipment",
            "parcel",
            "package",
            "courier",
            "tracking",
            "fast delivery",
            "delivery issue",
            "shipping delay",
        ],
        "medium": [
            "arrive",
            "arrival",
            "late",
            "delay",
            "dispatch",
            "received",
            "damaged package",
        ],
    },
    "sav": {
        "strong": [
            "customer support",
            "customer service",
            "support team",
            "helpful support",
            "great support",
            "refund request",
            "return request",
            "never answered",
            "no response",
            "seller support",
        ],
        "medium": [
            "support",
            "refund",
            "return",
            "response",
            "reply",
            "agent",
            "service",
            "warranty",
            "contact",
            "issue",
        ],
    },
    "produit": {
        "strong": [
            "product quality",
            "great product",
            "excellent product",
            "poor quality",
            "bad quality",
            "wrong size",
            "cheap material",
            "defective product",
            "broken product",
            "damaged item",
        ],
        "medium": [
            "product",
            "quality",
            "material",
            "fabric",
            "size",
            "fit",
            "broken",
            "damaged",
            "cheap",
            "design",
            "item",
            "comfortable",
        ],
    },
}

POSITIVE_TERMS = {
    "excellent",
    "great",
    "amazing",
    "perfect",
    "good",
    "love",
    "fast",
    "quick",
    "helpful",
    "resolved",
    "comfortable",
    "beautiful",
    "sturdy",
    "happy",
    "satisfied",
    "smooth",
}

NEGATIVE_TERMS = {
    "bad",
    "poor",
    "terrible",
    "awful",
    "slow",
    "late",
    "delayed",
    "broken",
    "damaged",
    "defective",
    "cheap",
    "thin",
    "frustrating",
    "disappointed",
    "refund",
    "return",
    "problem",
    "issue",
    "missing",
    "wrong",
    "never",
}

NEGATION_TERMS = {"not", "never", "no", "hardly", "barely", "n't"}


@dataclass
class ThemeResult:
    present: int
    sentiment: Optional[str]
    confidence: float
    evidence: List[str]


def normalize_text(text: str) -> str:
    text = str(text or "").lower().strip()
    return re.sub(r"\s+", " ", text)


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", normalize_text(text))


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
    cleaned = [normalize_text(part) for part in parts if normalize_text(part)]
    return cleaned or [normalize_text(text)]


def term_present(sentence: str, term: str) -> bool:
    term = normalize_text(term)
    if " " in term:
        return term in sentence
    return re.search(rf"\b{re.escape(term)}\b", sentence) is not None


def collect_theme_evidence(text: str, theme: str) -> Tuple[float, List[str]]:
    score = 0.0
    evidence: List[str] = []
    for sentence in split_sentences(text):
        sentence_score = 0.0
        for term in THEME_KEYWORDS[theme]["strong"]:
            if term_present(sentence, term):
                sentence_score += 0.28
                evidence.append(term)
        for term in THEME_KEYWORDS[theme]["medium"]:
            if term_present(sentence, term):
                sentence_score += 0.12
                evidence.append(term)
        score += min(sentence_score, 0.55)

    deduped: List[str] = []
    for item in evidence:
        if item not in deduped:
            deduped.append(item)
    return min(score, 0.98), deduped[:5]


def detect_themes(text: str, threshold: float = DEFAULT_THEME_THRESHOLD) -> Dict[str, ThemeResult]:
    normalized = normalize_text(text)
    results: Dict[str, ThemeResult] = {}
    for theme in THEME_KEYWORDS:
        confidence, evidence = collect_theme_evidence(normalized, theme)
        results[theme] = ThemeResult(
            present=int(confidence >= threshold),
            sentiment=None,
            confidence=round(confidence, 2),
            evidence=evidence,
        )
    return results


def score_sentence_sentiment(sentence: str) -> Tuple[int, List[str], List[str]]:
    tokens = tokenize(sentence)
    score = 0
    positives: List[str] = []
    negatives: List[str] = []
    for idx, token in enumerate(tokens):
        window = tokens[max(0, idx - 2): idx]
        negated = any(word in NEGATION_TERMS for word in window)
        if token in POSITIVE_TERMS:
            if negated:
                score -= 1
                negatives.append(f"not {token}")
            else:
                score += 1
                positives.append(token)
        elif token in NEGATIVE_TERMS:
            if negated:
                score += 1
                positives.append(f"not {token}")
            else:
                score -= 1
                negatives.append(token)
    return score, positives[:4], negatives[:4]


def score_sentiment(text: str) -> Tuple[str, float, List[str], List[str]]:
    total = 0
    positives: List[str] = []
    negatives: List[str] = []
    for sentence in split_sentences(text):
        sentence_score, pos, neg = score_sentence_sentiment(sentence)
        total += sentence_score
        positives.extend(pos)
        negatives.extend(neg)

    magnitude = abs(total)
    if total > 0:
        return "positive", round(min(0.52 + 0.12 * magnitude, 0.95), 2), positives[:5], negatives[:5]
    if total < 0:
        return "negative", round(min(0.52 + 0.12 * magnitude, 0.95), 2), positives[:5], negatives[:5]
    return "neutral", 0.5, positives[:5], negatives[:5]


def extract_theme_context(text: str, theme: str) -> str:
    sentences = split_sentences(text)
    terms = THEME_KEYWORDS[theme]["strong"] + THEME_KEYWORDS[theme]["medium"]
    matched = [sentence for sentence in sentences if any(term_present(sentence, term) for term in terms)]
    return " ".join(matched[:2]) if matched else normalize_text(text)


def score_theme_sentiment(text: str, theme: str) -> Tuple[str, float, List[str], List[str]]:
    return score_sentiment(extract_theme_context(text, theme))


def human_review_needed(theme_results: Dict[str, ThemeResult], global_confidence: float, text: str, threshold: float) -> bool:
    has_borderline = any(0.24 <= result.confidence < threshold for result in theme_results.values())
    short_text = len(tokenize(text)) < 4
    no_theme = not any(result.present == 1 for result in theme_results.values())
    uncertain_sentiment = global_confidence < 0.56
    return has_borderline or short_text or (no_theme and uncertain_sentiment)


def actionable_text(theme: str, sentiment: Optional[str]) -> str:
    mapping = {
        "livraison": {
            "negative": "Verifier les delais, le transporteur et l'etat des colis.",
            "positive": "Mettre en avant la fiabilite logistique dans le reporting CX.",
            "neutral": "Surveiller la logistique pour detecter des signaux recurrents.",
        },
        "sav": {
            "negative": "Escalader vers les operations support et revoir le temps de reponse.",
            "positive": "Utiliser ce retour comme preuve de qualite du support.",
            "neutral": "Observer les interactions support pour trouver des points faibles.",
        },
        "produit": {
            "negative": "Analyser qualite, sizing, matiere ou conformite produit.",
            "positive": "Valoriser ces points forts dans les insights produit.",
            "neutral": "Surveiller ce theme pour enrichir les categories analytiques.",
        },
    }
    key = sentiment if sentiment in {"negative", "positive", "neutral"} else "neutral"
    return mapping.get(theme, {}).get(key, "Surveiller ce theme.")


def analyze_review(text: str, review_id: str, threshold: float = DEFAULT_THEME_THRESHOLD) -> Dict:
    normalized = normalize_text(text)
    theme_results = detect_themes(normalized, threshold)
    global_sentiment, global_confidence, positive_terms, negative_terms = score_sentiment(normalized)

    detected_themes: List[str] = []
    theme_confidences: List[float] = []
    insights = []

    for theme, result in theme_results.items():
        if result.present == 1:
            detected_themes.append(theme)
            theme_sentiment, theme_confidence, _, _ = score_theme_sentiment(normalized, theme)
            combined_confidence = round(min(result.confidence * 0.6 + theme_confidence * 0.4, 0.98), 2)
            theme_results[theme] = ThemeResult(1, theme_sentiment, combined_confidence, result.evidence)
            theme_confidences.append(combined_confidence)
            insights.append(
                {
                    "topic": theme,
                    "sentiment": theme_sentiment,
                    "confidence": combined_confidence,
                    "evidence": result.evidence,
                    "actionable_text": actionable_text(theme, theme_sentiment),
                }
            )

    score_global = round(sum(theme_confidences) / len(theme_confidences), 2) if theme_confidences else round(global_confidence, 2)

    output = {
        "review_id": review_id,
        "review_text": text,
        "global_sentiment": global_sentiment,
        "score_global": score_global,
        "positive_terms": positive_terms,
        "negative_terms": negative_terms,
        "themes_detected": detected_themes,
        "needs_human_review": human_review_needed(theme_results, global_confidence, normalized, threshold),
        "insights": insights,
    }

    for theme, result in theme_results.items():
        output[f"theme_{theme}"] = result.present
        output[f"sent_{theme}"] = result.sentiment
        output[f"conf_{theme}"] = result.confidence
        output[f"evidence_{theme}"] = result.evidence

    return output
