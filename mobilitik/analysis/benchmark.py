from __future__ import annotations

from typing import Any

from mobilitik.company import normalize_company_input
from mobilitik.desktop.data import ComplaintRepository


def compare_companies(
    repo: ComplaintRepository,
    company1: str,
    company2: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """İki firmanın seçilen tarih aralığındaki performans metriklerini karşılaştırır."""
    c1 = normalize_company_input(company1)
    c2 = normalize_company_input(company2)

    m1 = repo.filtered_metrics(company=c1, start_date=start_date, end_date=end_date)
    m2 = repo.filtered_metrics(company=c2, start_date=start_date, end_date=end_date)

    def _rate(part: int, total: int) -> float:
        return round((part / total * 100), 1) if total > 0 else 0.0

    def _format_hours(hours: float | None) -> str:
        if hours is None:
            return "—"
        if hours < 24:
            return f"{hours:.1f} sa"
        return f"{hours / 24.0:.1f} gün"

    summary_rows = [
        {
            "metric": "Toplam Şikâyet",
            "c1_val": str(m1["total"]),
            "c2_val": str(m2["total"]),
        },
        {
            "metric": "Çözülen Şikâyet",
            "c1_val": f"{m1['resolved']} ({_rate(m1['resolved'], m1['total'])}%)",
            "c2_val": f"{m2['resolved']} ({_rate(m2['resolved'], m2['total'])}%)",
        },
        {
            "metric": "Firma Yanıtı",
            "c1_val": f"{m1['responded']} ({_rate(m1['responded'], m1['total'])}%)",
            "c2_val": f"{m2['responded']} ({_rate(m2['responded'], m2['total'])}%)",
        },
        {
            "metric": "Medyan Yanıt Süresi",
            "c1_val": _format_hours(m1["median_response_hours"]),
            "c2_val": _format_hours(m2["median_response_hours"]),
        },
        {
            "metric": "Medyan Çözüm Süresi",
            "c1_val": _format_hours(m1["median_resolution_hours"]),
            "c2_val": _format_hours(m2["median_resolution_hours"]),
        },
    ]

    return {
        "company1": {
            "name": c1,
            "metrics": m1,
            "resolution_rate": _rate(m1["resolved"], m1["total"]),
            "response_rate": _rate(m1["responded"], m1["total"]),
        },
        "company2": {
            "name": c2,
            "metrics": m2,
            "resolution_rate": _rate(m2["resolved"], m2["total"]),
            "response_rate": _rate(m2["responded"], m2["total"]),
        },
        "rows": summary_rows,
    }
