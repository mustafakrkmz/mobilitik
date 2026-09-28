from __future__ import annotations


def build_scrapy_args(
    company: str,
    start_date: str,
    end_date: str,
    max_pages: int,
) -> list[str]:
    company = company.strip().strip("/")
    if not company:
        raise ValueError("company is required")
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")
    if int(max_pages) < 1:
        raise ValueError("max_pages must be at least 1")

    return [
        "-m",
        "scrapy",
        "crawl",
        "complaints",
        "-a",
        f"company={company}",
        "-a",
        f"start_date={start_date}",
        "-a",
        f"end_date={end_date}",
        "-a",
        f"max_pages={int(max_pages)}",
    ]
