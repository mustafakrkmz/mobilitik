from __future__ import annotations

import datetime as dt
import json
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

COMPLAINT_BODY_SELECTORS = (
    "div.complaint-detail-description ::text",
    "[class*='complaint-detail-description'] ::text",
    "[class*='complaint-description'] ::text",
    "[data-testid*='complaint-description'] ::text",
    "[data-testid*='complaint-content'] ::text",
    "[data-testid*='complaint-body'] ::text",
    "article [class*='description'] ::text",
    "article [class*='content'] p ::text",
    "main [class*='description'] ::text",
    "main [class*='content'] p ::text",
)

# Şikayetvar uses this kind of sentence as an SEO/link-preview description.
# It is not the consumer complaint body and must never enter text analyses.
_BOILERPLATE_MARKERS = (
    "şikayetini ve yorumlarını okumak",
    "şikâyetini ve yorumlarını okumak",
    "hakkında şikayet yazmak için tıklayın",
    "hakkında şikâyet yazmak için tıklayın",
    "şikayetleri için tıklayın",
    "şikâyetleri için tıklayın",
    "visit to read complaints and reviews",
    "file yours",
)


def parse_sikayetvar_date(text: str, reference_date: dt.date | None = None) -> dt.datetime | None:
    return parse_datetime(text, reference_date=reference_date)


def _normalized_text(selector) -> str | None:
    parts = [part.strip() for part in selector.css("::text").getall() if part.strip()]
    value = " ".join(parts)
    return " ".join(value.split()) or None


def _clean_text(parts) -> str | None:
    value = " ".join(str(part).strip() for part in parts if str(part).strip())
    return " ".join(value.split()) or None


def _is_boilerplate_text(text: str | None) -> bool:
    if not text:
        return False
    lowered = " ".join(text.lower().split())
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _valid_complaint_candidate(text: str | None, *, min_length: int = 20) -> bool:
    if not text or len(text.strip()) < min_length:
        return False
    return not _is_boilerplate_text(text)


def _structured_complaint_text(response) -> str | None:
    """Read only structured fields that are intended to hold article/review body.

    Generic JSON-LD ``description`` is intentionally excluded because Sikayetvar
    currently uses it for SEO preview copy such as '... şikayetini ve yorumlarını
    okumak ...', which polluted previous Mobilitik analyses.
    """
    wanted = ("reviewBody", "articleBody")

    def walk(value):
        if isinstance(value, dict):
            for key in wanted:
                candidate = value.get(key)
                if isinstance(candidate, str):
                    candidate = " ".join(candidate.split())
                    if _valid_complaint_candidate(candidate, min_length=40):
                        return candidate
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None

    for raw in response.css('script[type="application/ld+json"]::text').getall():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        found = walk(parsed)
        if found:
            return found
    return None


def _long_paragraph_complaint_text(response) -> str | None:
    """Fallback for Sikayetvar's frequently changing detail-page class names.

    Consumer complaint bodies are generally substantial paragraph blocks. We rank
    visible paragraphs by length and reject known SEO/link-preview boilerplate.
    This is deliberately below explicit complaint selectors in priority.
    """
    candidates: list[str] = []
    selectors = (
        "main p ::text",
        "article p ::text",
        "main p::text",
        "article p::text",
    )
    for selector in selectors:
        # Each selector may return paragraph fragments. Keep each paragraph node
        # separate when possible so unrelated page text is not concatenated.
        node_selector = selector.replace(" ::text", "").replace("::text", "")
        for node in response.css(node_selector):
            text = _clean_text(node.css("::text").getall())
            if _valid_complaint_candidate(text, min_length=40):
                candidates.append(text)
    if not candidates:
        return None
    return max(candidates, key=len)


def _extract_complaint_text(response) -> str | None:
    for selector in COMPLAINT_BODY_SELECTORS:
        text = _clean_text(response.css(selector).getall())
        if _valid_complaint_candidate(text):
            return text

    paragraph_text = _long_paragraph_complaint_text(response)
    if paragraph_text:
        return paragraph_text

    return _structured_complaint_text(response)


def _listing_excerpt(card, title: str | None, normalized_card_text: str) -> str | None:
    # Current Sikayetvar listing cards expose the consumer's own complaint excerpt
    # in paragraph text. This is a safer fallback than SEO metadata on detail pages.
    for selector in (
        "p ::text",
        "p::text",
        "[data-testid*='description'] ::text",
        "[class*='description'] ::text",
    ):
        text = _clean_text(card.css(selector).getall())
        if _valid_complaint_candidate(text):
            return text[:2500]

    fallback = normalized_card_text
    if title and fallback.startswith(title):
        fallback = fallback[len(title):].strip()
    if _valid_complaint_candidate(fallback):
        return fallback[:2500]
    return None


def _event_from_containers(response, selectors: tuple[str, ...]) -> tuple[str | None, dt.datetime | None]:
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

    def __init__(self, company=None, start_date=None, end_date=None, start_page=1, max_pages=None, *args, **kwargs):
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
        yield self._listing_request(self.start_page)

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

    def _in_requested_range(self, value: dt.datetime | None) -> bool:
        if value is None:
            return True
        day = value.date()
        if self.start_date and day < self.start_date:
            return False
        if self.end_date and day > self.end_date:
            return False
        return True

    def parse_listing(self, response):
        page_num = response.meta["page_num"]
        if response.status in (403, 429):
            self.logger.error(
                "Şikayetvar erişimi HTTP %s ile engelledi. Bu bir veri-yok durumu değildir; site erişim kısıtı/Cloudflare olabilir. Mobilitik korumayı aşmaya çalışmaz.",
                response.status,
            )
            raise CloseSpider("site_access_blocked")

        page_text = " ".join(response.css("body ::text").getall()).lower()
        if "just a moment" in page_text or "checking your browser" in page_text:
            self.logger.error("Şikayetvar bir tarayıcı doğrulama/Cloudflare sayfası döndürdü. Mobilitik bu korumayı aşmaya çalışmaz.")
            raise CloseSpider("site_access_challenge")

        cards = response.css("article.ga-c.ga-v") or response.css("article.card-v2.ga-v.ga-c")
        if not cards:
            self.logger.error("Sayfa açıldı ancak şikâyet kartı bulunamadı (sayfa %s). Şikayetvar HTML yapısı değişmiş olabilir.", page_num)
            return

        detail_requests = 0
        skipped_by_date = 0
        for card in cards:
            href = card.css("h2.complaint-title a::attr(href)").get() or card.css("a::attr(href)").get()
            if not href or not href.startswith(f"/{self.company}/") or href.startswith("/uye/"):
                continue

            title_parts = card.css("h2.complaint-title a::text").getall()
            if not title_parts:
                links = card.css("a")
                first_link = links[0] if links else None
                listing_title = _normalized_text(first_link) if first_link is not None else None
            else:
                listing_title = _clean_text(title_parts)

            complaint_url = urljoin("https://www.sikayetvar.com", href)
            normalized_card_text = _clean_text(card.css("::text").getall()) or ""
            listing_resolved = "Çözüldü" in normalized_card_text
            listing_date = parse_datetime(normalized_card_text)
            listing_excerpt = _listing_excerpt(card, listing_title, normalized_card_text)

            if not self._in_requested_range(listing_date):
                skipped_by_date += 1
                continue

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
                    "listing_excerpt": listing_excerpt,
                },
            )

        self.logger.info("Page %s: queued %s complaint detail requests; skipped %s outside date range.", page_num, detail_requests, skipped_by_date)
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
        if parsed_date and not self._in_requested_range(parsed_date):
            self.logger.debug("Skipping complaint outside requested date range: %s", response.url)
            return

        title_parts = response.css("h1.complaint-detail-title ::text").getall() or response.css("h1 ::text").getall()
        title = _clean_text(title_parts) or response.meta.get("listing_title")

        detail_text = _extract_complaint_text(response)
        listing_excerpt = response.meta.get("listing_excerpt")
        complaint_text = detail_text if _valid_complaint_candidate(detail_text) else listing_excerpt
        if _is_boilerplate_text(complaint_text):
            complaint_text = None

        if not complaint_text:
            self.logger.warning(
                "Şikâyet gövdesi alınamadı; SEO önizleme metni analiz verisi olarak kaydedilmedi: %s",
                response.url,
            )

        resolved = bool(response.meta.get("listing_resolved"))

        company_response_text, company_response_date = _event_from_containers(response, RESPONSE_CONTAINER_SELECTORS)
        response_hours = elapsed_hours(parsed_date, company_response_date)
        if company_response_date is not None and response_hours is None:
            company_response_date = None

        resolution_text = None
        resolution_date = None
        resolution_hours = None
        if resolved:
            resolution_text, resolution_date = _event_from_containers(response, RESOLUTION_CONTAINER_SELECTORS)
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
