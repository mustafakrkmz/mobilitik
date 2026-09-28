import datetime as dt

from mobilitik.spiders.complaints import parse_sikayetvar_date


def test_date_with_explicit_year():
    parsed = parse_sikayetvar_date("31 Aralık 2025 18:24", reference_date=dt.date(2026, 9, 28))
    assert parsed == dt.datetime(2025, 12, 31, 18, 24)


def test_date_without_year_uses_current_year_when_plausible():
    parsed = parse_sikayetvar_date("28 Eylül 12:10", reference_date=dt.date(2026, 9, 28))
    assert parsed == dt.datetime(2026, 9, 28, 12, 10)


def test_date_without_year_rolls_back_when_far_in_future():
    parsed = parse_sikayetvar_date("31 Aralık 18:24", reference_date=dt.date(2026, 9, 28))
    assert parsed == dt.datetime(2025, 12, 31, 18, 24)


def test_invalid_date_returns_none():
    assert parse_sikayetvar_date("bugün") is None
