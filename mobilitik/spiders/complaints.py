from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

import scrapy
from scrapy.exceptions import CloseSpider

from mobilitik.company import normalize_company_input
from mobilitik.timing import elapsed_hours, first_datetime, parse_datetime


RESPONSE_CONTAINER_SELECTORS = (
    ".brand-answer",
    ".company-response",
    ".complaint-detail-brand-response",
    "[class*='brand-answer']",
    "[class*='brand-response']",
    "[class*='company-response']",
    "[data-testid*='brand-answer']",
    "[data-testid*='company-response']",
)

RESOLUTION_CONTAINER_SELECTORS = (
    ".complaint-solution",
    ".complaint-result",
    ".solution-detail",
    ".resolution-detail",
    "[class*='complaint-solution']",
    "[class*='complaint-result']",
    "[data-testid*='solution']",
    "[data-testid*='resolution']",
)

DATE_VALUE_SELECTORS = (
    "time::attr(datetime)",
    "[datetime]::attr(datetime)",
    "time::text",
    ".date::text",
    ".post-time ::text",
    "[class*='date']::text",
    "[class*='time']::text",
)


def parse_sikayetvar_date(text: str, reference_date: dt.date | None = None) -> dt.datetime | None:
    """Backward-compatible wrapper for the shared date parser."""
    return parse_datetime(text, reference_date=reference_date)


def _normalized_text(selector) -> str | None:
    parts = [part.strip() for part in selector.css("::text").getall() if part.strip()]
    value = " ".join(parts)
    return " ".join(value.split()) or None


def _event_from_containers(response, selectors: tuple[str, ...]) -> tuple[str | None, dt.datetime | None]:
    """Return the first meaningful event text and an explicit date when present."""
    fallback_text: str | None = None
    for selector in selectors:
        for node in response.css(selector):
            text = _normalized_text(node)
            if text and fallback_text is None:
                fallback_text = text

            values: list[str | None] = []
            for date_selector in DATE_VALUE_SELECTORS:
                values.extend(node.css(date_selector).getall())
            if text:
                values.append(text)

            event_date = first_datetime(values)
            if event_date is not None:
                return text, event_date

    return fallback_text, None


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
        "HTTPERROR_ALLOWED_CODES": [403, 429],
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
        try:
            self.company = normalize_company_input(company or "")
        except ValueError as exc:
            raise CloseSpider(str(exc)) from exc

        self.start_page = int(start_page)
        self.max_pages = int(max_pages) if max_pages else None
        self.items_collected = 0

        self.start_date = dt.datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        self.end_date = dt.datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise CloseSpider("start_date cannot be after end_date")

    async def start(self):
        """Yield the initial request using the Scrapy 2.13+ start API."""
        yield self._listing_request(self.start_page)

    def start_requests(self):
        """Compatibility fallback for Scrapy versions older than 2.13."""
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

        if response.status in (403, 429):
            self.logger.error(
                "Şikayetvar erişimi HTTP %s ile engelledi. Bu bir veri-yok durumu değildir; "
                "site erişim kısıtı/Cloudflare olabilir. Mobilitik korumayı aşmaya çalışmaz.",
                response.status,
            )
            raise CloseSpider("site_access_blocked")

        page_text = " ".join(response.css("body ::text").getall()).lower()
        if "just a moment" in page_text or "checking your browser" in page_text:
            self.logger.error(
                "Şikayetvar bir tarayıcı doğrulama/Cloudflare sayfası döndürdü. "
                "Mobilitik bu korumayı aşmaya çalışmaz."
            )
            raise CloseSpider("site_access_challenge")

        cards = response.css("article.ga-c.ga-v")
        if not cards:
            cards = response.css("article.card-v2.ga-v.ga-c")

        if not cards:
            self.logger.error(
                "Sayfa açıldı ancak şikâyet kartı bulunamadı (sayfa %s). "
                "Şikayetvar HTML yapısı değişmiş olabilir.",
                page_num,
            )
            return

        detail_requests = 0
        for card in cards:
            href = (
                card.css("h2.complaint-title a::attr(href)").get()
                or card.css("a::attr(href)").get()
            )
            if not href or not href.startswith(f"/{self.company}/") or href.startswith("/uye/"):
                continue

            title_parts = card.css("h2.complaint-title a::text").getall()
            if not title_parts:
                links = card.css("a")
                first_link = links[0] if links else None
                listing_title = _normalized_text(first_link) if first_link is not None else None
            else:
                listing_title = " ".join(p.strip() for p in title_parts if p.strip()) or None

            complaint_url = urljoin("https://www.sikayetvar.com", href)
            card_text = " ".join(card.css("::text").getall())
            normalized_card_text = " ".join(card_text.split())
            listing_resolved = "Çözüldü" in normalized_card_text
            listing_date = parse_datetime(normalized_card_text)

            detail_requests += 1
            yield scrapy.Request(
                complaint_url,
                callback=self.parse_complaint,
                meta={
                    "ref_url": complaint_url,
                    "listing_page": page_num,
                    "listing_resolved": listing_resolved,
                    "listing_title": listing_title,
                    "listing_date": listing_date.isoformat(sep=" ") if listing_date else None,
                },
            )

        self.logger.info("Page %s: queued %s complaint detail requests.", page_num, detail_requests)

        if self.max_pages and page_num >= self.start_page + self.max_pages - 1:
            return

        yield self._listing_request(page_num + 1)

    def parse_complaint(self, response):
        if response.status in (403, 429):
            self.logger.warning("Şikâyet detayına erişilemedi (HTTP %s): %s", response.status, response.url)
            return

        date_text = response.css("div.post-time div::text").get()
        parsed_date = parse_sikayetvar_date(date_text) if date_text else None
        if parsed_date is None:
            parsed_date = parse_datetime(response.meta.get("listing_date"))

        if self.start_date and parsed_date and parsed_date.date() < self.start_date:
            raise CloseSpider("date range completed")
        if self.end_date and parsed_date and parsed_date.date() > self.end_date:
            return

        title_parts = response.css("h1.complaint-detail-title ::text").getall()
        body_parts = response.css("div.complaint-detail-description ::text").getall()

        title = " ".join(p.strip() for p in title_parts if p.strip()) or response.meta.get("listing_title")
        complaint_text = " ".join(p.strip() for p in body_parts if p.strip()) or None
        resolved = bool(response.meta.get("listing_resolved"))

        company_response_text, company_response_date = _event_from_containers(
            response, RESPONSE_CONTAINER_SELECTORS
        )
        response_hours = elapsed_hours(parsed_date, company_response_date)
        if company_response_date is not None and response_hours is None:
            company_response_date = None

        resolution_text: str | None = None
        resolution_date: dt.datetime | None = None
        resolution_hours: float | None = None
        if resolved:
            resolution_text, resolution_date = _event_from_containers(
                response, RESOLUTION_CONTAINER_SELECTORS
            )
            resolution_hours = elapsed_hours(parsed_date, resolution_date)
            if resolution_date is not None and resolution_hours is None:
                resolution_date = None

        self.items_collected += 1
        yield {
            "company": self.company,
            "complaint_url": response.meta["ref_url"],
            "complaint_date": parsed_date.isoformat(sep=" ") if parsed_date else None,
            "title": title,
            "complaint_text": complaint_text,
            "resolved": resolved,
            "company_responded": bool(company_response_text or company_response_date),
            "company_response_text": company_response_text,
            "company_response_date": company_response_date.isoformat(sep=" ") if company_response_date else None,
            "response_hours": response_hours,
            "resolution_text": resolution_text,
            "resolution_date": resolution_date.isoformat(sep=" ") if resolution_date else None,
            "resolution_hours": resolution_hours,
            "listing_page": response.meta["listing_page"],
            "scraped_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
