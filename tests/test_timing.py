import datetime as dt

from mobilitik.timing import elapsed_hours, first_datetime, median, parse_datetime


def test_parse_datetime_supports_turkish_embedded_text():
    parsed = parse_datetime(
        "Marka Yanıtı 2 Ocak 2026 03:30",
        reference_date=dt.date(2026, 9, 28),
    )
    assert parsed == dt.datetime(2026, 1, 2, 3, 30)


def test_parse_datetime_supports_iso_and_numeric_dates():
    assert parse_datetime("2026-09-28T14:30:00") == dt.datetime(2026, 9, 28, 14, 30)
    assert parse_datetime("28.09.2026 14:30") == dt.datetime(2026, 9, 28, 14, 30)


def test_first_datetime_skips_non_dates():
    parsed = first_datetime(["Marka yanıtı", None, "28 Eylül 12:10"], reference_date=dt.date(2026, 9, 28))
    assert parsed == dt.datetime(2026, 9, 28, 12, 10)


def test_elapsed_hours_rejects_negative_duration():
    start = dt.datetime(2026, 1, 1, 10, 0)
    assert elapsed_hours(start, dt.datetime(2026, 1, 1, 13, 30)) == 3.5
    assert elapsed_hours(start, dt.datetime(2026, 1, 1, 9, 0)) is None
    assert elapsed_hours(None, start) is None


def test_median_ignores_missing_values():
    assert median([1, None, 3, 5]) == 3.0
    assert median([1, 3]) == 2.0
    assert median([None]) is None
