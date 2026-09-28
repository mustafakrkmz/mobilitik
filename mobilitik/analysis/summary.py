from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Any

from mobilitik.timing import median

from .classifier import classify_record


def category_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "complaints": 0,
            "resolved": 0,
            "responded": 0,
            "response_hours": [],
            "resolution_hours": [],
        }
    )

    for row in rows:
        result = classify_record(row.get("title"), row.get("complaint_text"))
        categories = result.categories or ["Diğer"]
        for category in categories:
            bucket = buckets[category]
            bucket["complaints"] += 1
            bucket["resolved"] += int(bool(row.get("resolved")))
            bucket["responded"] += int(bool(row.get("company_responded")))
            if row.get("response_hours") is not None:
                bucket["response_hours"].append(row.get("response_hours"))
            if row.get("resolution_hours") is not None:
                bucket["resolution_hours"].append(row.get("resolution_hours"))

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
                "median_response_hours": median(values["response_hours"]),
                "median_resolution_hours": median(values["resolution_hours"]),
                "timed_responses": len(values["response_hours"]),
                "timed_resolutions": len(values["resolution_hours"]),
            }
        )

    return sorted(summary, key=lambda item: (-item["complaints"], item["category"]))
