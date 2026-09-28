from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

import scrapy
from scrapy.exceptions import CloseSpider


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


def parse_sikayetvar_date(text: str, reference_date: dt.date | None = None) -> dt.datetime | None:
    """Parse Şikayetvar date strings.

    Supported examples:
    - ``28 Eylül 12:10``
    - ``31 Aralık 2025 18:24``

    When the year is omitted, infer it relative to the crawl date. If the
    resulting month/day would lie implausibly far in the future, use the
    previous year instead.
    """
    reference_date = reference_date or dt.date.today()
    try:
        parts = text.strip().split()
        if len(parts) not in (3, 4):
            return None

        day = int(parts[0])
        month = TURKISH_MONTHS[parts[1]]

        if len(parts) == 4:
            year = int(parts[2])
            time_part = parts[3]
        else:
            year = reference_date.year
            time_part = parts[2]

        hour, minute = map(int, time_part.split(":"))
        candidate = dt.datetime(year, month, day, hour, minute)

        if len(parts) == 3 and candidate.date() > reference_date + dt.timedelta(days=31):
            candidate = candidate.replace(year=reference_date.year - 1)

        return candidate
    except (ValueError, KeyError, IndexError):
        return None


class ComplaintSpider(scrapy.Spider):
    name = "complaints"
    allowed_domains = ["sikayetvar.com", "www.sikayetvar.com"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.5,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": "Mobilitik academic research crawler/0.1",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60_000,
    }

    def __init__(
        self,
        company: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        start_page: int | str = 1,
        max_pages: int | str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if not company:
            raise CloseSpider("company parameter is required")

        self.company = company.strip("/")
        self.start_page = int(start_page)
        self.max_pages = int(max_pages) if max_pages else None
        self.items_collected = 0

        self.start_date = dt.datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        self.end_date = dt.datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise CloseSpider("start_date cannot be after end_date")

    def start_requests(self):
        yield self._listing_request(self.start_page)

    def _listing_request(self, page: int):
        url = f"https://www.sikayetvar.com/{self.company}?page={page}"
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={
                "page_num": page,
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            },
        )

    def parse_listing(self, response):
        page_num = response.meta["page_num"]
        cards = response.css("article.card-v2.ga-v.ga-c")

        if not cards:
            self.logger.info("No complaint cards found on page %s; stopping.", page_num)
            return

        for card in cards:
            href = card.css("h2.complaint-title a::attr(href)").get()
            if not href:
                continue

            complaint_url = urljoin("https://www.sikayetvar.com", href)
            card_text = " ".join(card.css("::text").getall())
            normalized_card_text = " ".join(card_text.split())
            listing_resolved = "Çözüldü" in normalized_card_text

            yield scrapy.Request(
                complaint_url,
                callback=self.parse_complaint,
                meta={
                    "ref_url": complaint_url,
                    "listing_page": page_num,
                    "listing_resolved": listing_resolved,
                },
            )

        if self.max_pages and page_num >= self.start_page + self.max_pages - 1:
            return

        yield self._listing_request(page_num + 1)

    def parse_complaint(self, response):
        date_text = response.css("div.post-time div::text").get()
        parsed_date = parse_sikayetvar_date(date_text) if date_text else None

        if self.start_date and parsed_date and parsed_date.date() < self.start_date:
            raise CloseSpider("date range completed")
        if self.end_date and parsed_date and parsed_date.date() > self.end_date:
            return

        title_parts = response.css("h1.complaint-detail-title ::text").getall()
        body_parts = response.css("div.complaint-detail-description ::text").getall()

        title = " ".join(p.strip() for p in title_parts if p.strip()) or None
        complaint_text = " ".join(p.strip() for p in body_parts if p.strip()) or None

        # The resolved marker is associated with the complaint card on listing
        # pages. Reading it there avoids false positives caused by unrelated
        # 'Çözüldü' text elsewhere on a detail page.
        resolved = bool(response.meta.get("listing_resolved"))

        company_response_parts = response.css(
            ".brand-answer ::text, .company-response ::text, .complaint-detail-brand-response ::text"
        ).getall()
        company_response_text = " ".join(
            p.strip() for p in company_response_parts if p.strip()
        ) or None

        self.items_collected += 1
        yield {
            "company": self.company,
            "complaint_url": response.meta["ref_url"],
            "complaint_date": parsed_date.isoformat(sep=" ") if parsed_date else None,
            "title": title,
            "complaint_text": complaint_text,
            "resolved": resolved,
            "company_responded": bool(company_response_text),
            "company_response_text": company_response_text,
            "listing_page": response.meta["listing_page"],
            "scraped_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
