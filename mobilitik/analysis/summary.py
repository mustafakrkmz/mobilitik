from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Any

from .classifier import classify_record


def category_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"complaints": 0, "resolved": 0, "responded": 0})

    for row in rows:
        result = classify_record(row.get("title"), row.get("complaint_text"))
        categories = result.categories or ["Diğer"]
        for category in categories:
            bucket = buckets[category]
            bucket["complaints"] += 1
            bucket["resolved"] += int(bool(row.get("resolved")))
            bucket["responded"] += int(bool(row.get("company_responded")))

    summary: list[dict[str, Any]] = []
    for category, values in buckets.items():
        total = values["complaints"]
        summary.append(
            {
                "category": category,
                "complaints": total,
                "resolved": values["resolved"],
                "responded": values["responded"],
                "resolved_rate": (values["resolved"] / total * 100) if total else 0.0,
                "response_rate": (values["responded"] / total * 100) if total else 0.0,
            }
        )

    return sorted(summary, key=lambda item: (-item["complaints"], item["category"]))
