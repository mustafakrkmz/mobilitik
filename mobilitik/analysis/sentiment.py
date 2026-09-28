from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .classifier import classify_record


DEFAULT_MODEL_ID = "incidelen/bert-base-turkish-sentiment-analysis-cased"
ANALYZER_VERSION = "mobilitik-sentiment-v1"


@dataclass(frozen=True)
class SentimentScores:
    label: str
    confidence: float
    negative: float
    neutral: float
    positive: float


@dataclass(frozen=True)
class AspectSentiment:
    category: str
    sentence_count: int
    negative: float
    neutral: float
    positive: float


def complaint_text(title: str | None, body: str | None) -> str:
    return " ".join(part.strip() for part in (title or "", body or "") if part and part.strip()).strip()


def text_fingerprint(title: str | None, body: str | None) -> str:
    payload = complaint_text(title, body).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def split_sentences(text: str) -> list[str]:
    """A conservative Turkish-friendly sentence splitter for complaint prose."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\s*[\r\n]+\s*", cleaned)
    return [part.strip() for part in parts if part and part.strip()]


def _canonical_label(label: str) -> str | None:
    normalized = (label or "").strip().casefold()
    mapping = {
        "negative": "negative",
        "negatif": "negative",
        "label_0": "negative",
        "neutral": "neutral",
        "nötr": "neutral",
        "notr": "neutral",
        "label_1": "neutral",
        "positive": "positive",
        "pozitif": "positive",
        "label_2": "positive",
    }
    return mapping.get(normalized)


def scores_from_pipeline_output(rows: Sequence[Mapping[str, object]]) -> SentimentScores:
    """Normalize Hugging Face pipeline class scores to Mobilitik labels."""
    values = {"negative": 0.0, "neutral": 0.0, "positive": 0.0}
    for row in rows:
        canonical = _canonical_label(str(row.get("label", "")))
        if canonical is None:
            continue
        try:
            values[canonical] = float(row.get("score", 0.0))
        except (TypeError, ValueError):
            values[canonical] = 0.0

    total = sum(values.values())
    if total <= 0:
        raise ValueError("Model çıktısında Negative/Neutral/Positive skorları bulunamadı.")

    normalized = {name: value / total for name, value in values.items()}
    label = max(normalized, key=normalized.get)
    return SentimentScores(
        label=label,
        confidence=normalized[label],
        negative=normalized["negative"],
        neutral=normalized["neutral"],
        positive=normalized["positive"],
    )


def sentiment_label_tr(label: str) -> str:
    return {
        "negative": "Negatif",
        "neutral": "Nötr",
        "positive": "Pozitif",
    }.get(label, label)


def aspect_sentence_map(title: str | None, body: str | None) -> list[tuple[str, list[str]]]:
    """Attach manual Mobilitik categories to individual complaint sentences."""
    mapped: list[tuple[str, list[str]]] = []
    for sentence in split_sentences(complaint_text(title, body)):
        result = classify_record(sentence, None)
        categories = result.categories or ["Diğer"]
        mapped.append((sentence, categories))
    return mapped


def aggregate_aspect_sentiment(
    sentence_rows: Iterable[tuple[Sequence[str], SentimentScores]],
) -> list[AspectSentiment]:
    buckets: dict[str, list[SentimentScores]] = defaultdict(list)
    for categories, scores in sentence_rows:
        for category in categories:
            buckets[str(category)].append(scores)

    result: list[AspectSentiment] = []
    for category, rows in buckets.items():
        count = len(rows)
        result.append(
            AspectSentiment(
                category=category,
                sentence_count=count,
                negative=sum(row.negative for row in rows) / count,
                neutral=sum(row.neutral for row in rows) / count,
                positive=sum(row.positive for row in rows) / count,
            )
        )
    return sorted(result, key=lambda row: (-row.sentence_count, row.category))


def priority_score(
    issue_share: float,
    mean_negative: float,
    unresolved_rate: float,
    *,
    frequency_weight: float = 40.0,
    negativity_weight: float = 35.0,
    unresolved_weight: float = 25.0,
) -> float:
    """Transparent, user-weightable development-priority heuristic (0-100)."""
    weights = [frequency_weight, negativity_weight, unresolved_weight]
    if any(weight < 0 for weight in weights):
        raise ValueError("Öncelik ağırlıkları negatif olamaz.")
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0

    values = [
        max(0.0, min(1.0, float(issue_share))),
        max(0.0, min(1.0, float(mean_negative))),
        max(0.0, min(1.0, float(unresolved_rate))),
    ]
    weighted = sum(value * weight for value, weight in zip(values, weights)) / total_weight
    return weighted * 100.0
