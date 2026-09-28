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
    "company_url,expected",
    [
        ("https://www.sikayetvar.com/cilek-mobilya", "company=cilek-mobilya"),
        ("https://www.sikayetvar.com/konfor-mobilya/", "company=konfor-mobilya"),
        ("sikayetvar.com/cilek-mobilya", "company=cilek-mobilya"),
    ],
)
def test_build_scrapy_args_accepts_company_root_url(company_url, expected):
    args = build_scrapy_args(company_url, "2026-01-01", "2026-09-28", 2)
    assert expected in args


@pytest.mark.parametrize(
    "company,start,end,pages",
    [
        ("", "2026-01-01", "2026-09-28", 3),
        ("istikbal", "2026-10-01", "2026-09-28", 3),
        ("istikbal", "2026-01-01", "2026-09-28", 0),
        ("https://example.com/cilek-mobilya", "2026-01-01", "2026-09-28", 3),
        ("https://www.sikayetvar.com/cilek-mobilya/calisma-masasi", "2026-01-01", "2026-09-28", 3),
    ],
)
def test_build_scrapy_args_rejects_invalid_input(company, start, end, pages):
    with pytest.raises(ValueError):
        build_scrapy_args(company, start, end, pages)
