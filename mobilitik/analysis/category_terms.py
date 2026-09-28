from __future__ import annotations

from typing import Any, Iterable, Mapping

from .classifier import classify_record
from .textstats import TermScore, TextAnalyzer, distinctive_terms


def category_distinctive_terms(
    rows: Iterable[Mapping[str, Any]],
    *,
    n: int = 2,
    top_k: int = 15,
) -> dict[str, list[TermScore]]:
    """Find terms that are comparatively distinctive for complaint categories.

    ``Tümü`` contains TF-IDF-ranked terms across all selected complaints.
    Other entries contain terms that are comparatively distinctive for each
    manually configured complaint category. A complaint may contribute to more
    than one category because Mobilitik uses multi-label classification.
    """
    source_rows = list(rows)
    grouped: dict[str, list[str]] = {}
    all_documents: list[str] = []

    for row in source_rows:
        title = row.get("title") or ""
        body = row.get("complaint_text") or ""
        text = f"{title} {body}".strip()
        all_documents.append(text)
        result = classify_record(title, body)
        categories = result.categories or ["Diğer"]
        for category in categories:
            grouped.setdefault(category, []).append(text)

    if not source_rows:
        return {}

    result = {"Tümü": TextAnalyzer(all_documents).tfidf(n=n, top_k=top_k, min_doc_freq=1)}
    if grouped:
        result.update(distinctive_terms(grouped, n=n, top_k=top_k))
    return result
