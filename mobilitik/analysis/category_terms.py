from __future__ import annotations

from typing import Any, Iterable, Mapping

from .classifier import classify_record
from .textstats import TermScore, distinctive_terms


def category_distinctive_terms(
    rows: Iterable[Mapping[str, Any]],
    *,
    n: int = 2,
    top_k: int = 15,
) -> dict[str, list[TermScore]]:
    """Find terms that are comparatively distinctive for complaint categories.

    A complaint may contribute to multiple categories because Mobilitik uses
    multi-label classification. Records without a matched category are grouped
    under ``Diğer``.
    """
    grouped: dict[str, list[str]] = {}

    for row in rows:
        title = row.get("title") or ""
        body = row.get("complaint_text") or ""
        text = f"{title} {body}".strip()
        result = classify_record(title, body)
        categories = result.categories or ["Diğer"]
        for category in categories:
            grouped.setdefault(category, []).append(text)

    if not grouped:
        return {}

    return distinctive_terms(grouped, n=n, top_k=top_k)
