import pytest

from mobilitik.desktop.commands import build_scrapy_args


def test_build_scrapy_args():
    args = build_scrapy_args("/istikbal/", "2026-01-01", "2026-09-28", 3)
    assert args[:4] == ["-m", "scrapy", "crawl", "complaints"]
    assert "company=istikbal" in args
    assert "start_date=2026-01-01" in args
    assert "end_date=2026-09-28" in args
    assert "max_pages=3" in args


@pytest.mark.parametrize(
    "company,start,end,pages",
    [
        ("", "2026-01-01", "2026-09-28", 3),
        ("istikbal", "2026-10-01", "2026-09-28", 3),
        ("istikbal", "2026-01-01", "2026-09-28", 0),
    ],
)
def test_build_scrapy_args_rejects_invalid_input(company, start, end, pages):
    with pytest.raises(ValueError):
        build_scrapy_args(company, start, end, pages)
