from __future__ import annotations

import datetime as dt
import re
from typing import Iterable


TURKISH_MONTHS = {
    "Ocak": 1,
    "Şubat": 2,
    "Mart": 3,
    "Nisan": 4,
    "Mayıs": 5,
    "Haziran": 6,
    "Temmuz": 7,
    "Ağustos": 8,
    "Eylül": 9,
    "Ekim": 10,
    "Kasım": 11,
    "Aralık": 12,
}

_MONTH_PATTERN = "|".join(TURKISH_MONTHS)
_TR_DATE_RE = re.compile(
    rf"(?P<day>\d{{1,2}})\s+(?P<month>{_MONTH_PATTERN})(?:\s+(?P<year>\d{{4}}))?\s+(?P<hour>\d{{1,2}}):(?P<minute>\d{{2}})",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{4})(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?"
)


def _month_number(name: str) -> int | None:
    folded = name.casefold()
    for month_name, number in TURKISH_MONTHS.items():
        if month_name.casefold() == folded:
            return number
    return None


def parse_datetime(text: str | None, reference_date: dt.date | None = None) -> dt.datetime | None:
    """Parse ISO, numeric and Turkish Şikayetvar-style date strings.

    A year omitted from a Turkish date is inferred relative to ``reference_date``.
    The parser deliberately returns ``None`` instead of guessing when the input
    does not contain a recognizable date/time.
    """
    if not text:
        return None
    reference_date = reference_date or dt.date.today()
    value = " ".join(str(text).strip().split())

    iso_candidate = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

    match = _TR_DATE_RE.search(value)
    if match:
        month = _month_number(match.group("month"))
        if month is None:
            return None
        year = int(match.group("year")) if match.group("year") else reference_date.year
        candidate = dt.datetime(
            year,
            month,
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
        )
        if match.group("year") is None and candidate.date() > reference_date + dt.timedelta(days=31):
            candidate = candidate.replace(year=reference_date.year - 1)
        return candidate

    match = _NUMERIC_DATE_RE.search(value)
    if match:
        return dt.datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour") or 0),
            int(match.group("minute") or 0),
        )
    return None


def first_datetime(values: Iterable[str | None], reference_date: dt.date | None = None) -> dt.datetime | None:
    for value in values:
        parsed = parse_datetime(value, reference_date=reference_date)
        if parsed is not None:
            return parsed
    return None


def elapsed_hours(start: dt.datetime | None, end: dt.datetime | None) -> float | None:
    """Return non-negative elapsed hours, otherwise ``None``."""
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() / 3600.0, 2)


def median(values: Iterable[float | int | None]) -> float | None:
    cleaned = sorted(float(value) for value in values if value is not None)
    if not cleaned:
        return None
    middle = len(cleaned) // 2
    if len(cleaned) % 2:
        return round(cleaned[middle], 2)
    return round((cleaned[middle - 1] + cleaned[middle]) / 2.0, 2)
