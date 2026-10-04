from __future__ import annotations

import datetime as dt
import json
from urllib.parse import urljoin

import scrapy
from scrapy.exceptions import CloseSpider

from mobilitik.company import normalize_company_input
from mobilitik.text_quality import is_boilerplate_complaint_text, sanitize_complaint_body
from mobilitik.timing import elapsed_hours, first_datetime, parse_datetime


RESPONSE_CONTAINER_SELECTORS = (
    "div[class*='bg-indigo-50']",
    "div[class*='border-primary'][class*='border-l-']",
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
    "span[class*='text-zinc-500']::text",
    "div.text-muted-foreground.text-xs::text",
    "time::text",
    ".date::text",
    "div.post-time div::text",
    ".post-time ::text",
    "[class*='date']::text",
    "[class*='time']::text",
)

COMPLAINT_BODY_SELECTORS = (
    "article:first-of-type div[class*='mt-4'] p ::text",
    "article:first-of-type div[class*='font-normal'] p ::text",
    "div[class*='mt-4'][class*='md:mt-5'] p ::text",
    "div.selection-share p ::text",
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


def parse_sikayetvar_date(text: str, reference_date: dt.date | None = None) -> dt.datetime | None:
    return parse_datetime(text, reference_date=reference_date)


def _normalized_text(selector) -> str | None:
    parts = [part.strip() for part in selector.css("::text").getall() if part.strip()]
    value = " ".join(parts)
    return " ".join(value.split()) or None


def _clean_text(parts) -> str | None:
    value = " ".join(str(part).strip() for part in parts if str(part).strip())
    return " ".join(value.split()) or None


def _valid_complaint_candidate(text: str | None, *, min_length: int = 1) -> bool:
    if not text or len(text.strip()) < min_length:
        return False
    return not is_boilerplate_complaint_text(text)


def _structured_complaint_text(response) -> str | None:
    """Read structured JSON-LD fields (DiscussionForumPosting, Review, Article) holding complaint text."""
    for raw in response.css('script[type="application/ld+json"]::text').getall():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

        if isinstance(parsed, dict):
            me = parsed.get("mainEntity")
            if isinstance(me, dict):
                text = me.get("text")
                if isinstance(text, str) and _valid_complaint_candidate(text, min_length=20):
                    return text.strip()

                # For video complaints or threaded posts, check consumer comments
                comments = me.get("comment", [])
                if isinstance(comments, list):
                    consumer_parts = []
                    for c in comments:
                        if isinstance(c, dict):
                            author = c.get("author", {})
                            author_type = author.get("@type") if isinstance(author, dict) else ""
                            c_text = c.get("text", "")
                            if author_type == "Person" and _valid_complaint_candidate(c_text, min_length=20):
                                consumer_parts.append(c_text.strip())
                    if consumer_parts:
                        return "\n\n".join(consumer_parts)

        # Legacy walk for reviewBody / articleBody
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

        found = walk(parsed)
        if found:
            return found
    return None


def _all_article_paragraphs(response) -> str | None:
    """Extract all consecutive consumer paragraphs, preserving full multi-paragraph text."""
    articles = response.css("article")
    target = articles[0] if articles else response.css("main") or response

    paragraphs: list[str] = []
    for p_node in target.css("div[class*='mt-4'] p, div[class*='font-normal'] p, p"):
        text = _clean_text(p_node.css("::text").getall())
        if not text or len(text) < 15:
            continue
        if is_boilerplate_complaint_text(text):
            continue
        lower = text.lower()
        if any(marker in lower for marker in ("değerli müşterimiz", "sayın ilgili", "tüketici hizmetleri")):
            break
        if text not in paragraphs:
            paragraphs.append(text)

    if paragraphs:
        return "\n\n".join(paragraphs)
    return None


def _extract_complaint_text(response) -> str | None:
    # 1. Prefer structured JSON-LD data: pristine, complete, contains all paragraphs
    structured_text = _structured_complaint_text(response)
    if structured_text:
        return structured_text

    # 2. Modern and legacy CSS selectors for container
    for selector in COMPLAINT_BODY_SELECTORS:
        text = _clean_text(response.css(selector).getall())
        if _valid_complaint_candidate(text):
            return text

    # 3. Multi-paragraph article text extraction
    all_paras = _all_article_paragraphs(response)
    if all_paras and _valid_complaint_candidate(all_paras):
        return all_paras

    return None


def _listing_excerpt(card, title: str | None, normalized_card_text: str) -> str | None:
    for selector in (
        "p ::text",
        "p::text",
        "[data-testid*='description'] ::text",
        "[class*='description'] ::text",
    ):
        text = _clean_text(card.css(selector).getall())
        if _valid_complaint_candidate(text, min_length=20):
            return text[:2500]

    fallback = normalized_card_text
    if title and fallback.startswith(title):
        fallback = fallback[len(title):].strip()
    if _valid_complaint_candidate(fallback, min_length=20):
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

        cards = response.css("article")
        if not cards:
            cards = response.css("article.ga-c.ga-v") or response.css("article.card-v2.ga-v.ga-c") or response.css("[class*='card']")
        if not cards:
            self.logger.error("Sayfa açıldı ancak şikâyet kartı bulunamadı (sayfa %s). Şikayetvar HTML yapısı değişmiş olabilir.", page_num)
            return

        detail_requests = 0
        skipped_by_date = 0
        parsed_dates: list[dt.date] = []
        for card in cards:
            href = None
            listing_title = None

            # 1. Heading links (h3 a, h2 a, [class*='title'] a)
            for link_node in card.css("h3 a, h2 a, [class*='title'] a, a:has(h3), a:has(h2)"):
                c_href = link_node.css("::attr(href)").get()
                if c_href and c_href.startswith(f"/{self.company}/") and not c_href.startswith("/uye/"):
                    href = c_href
                    listing_title = _clean_text(link_node.css("::text").getall()) or link_node.attrib.get("title")
                    break

            # 2. Links with title attribute (video cards, Tailwind cards)
            if not href:
                for a in card.css("a[title]"):
                    c_href = a.attrib.get("href", "")
                    if c_href.startswith(f"/{self.company}/") and not c_href.startswith("/uye/"):
                        href = c_href
                        listing_title = a.attrib.get("title")
                        break

            # 3. Any link under /{self.company}/ that is not a category/section link
            if not href:
                for a in card.css("a"):
                    c_href = a.attrib.get("href", "")
                    if c_href.startswith(f"/{self.company}/") and not c_href.startswith("/uye/"):
                        slug = c_href[len(self.company) + 2:].strip("/")
                        if slug and slug not in ("fiyat", "kampanya", "magazalar", "yorumlar", "iletisim") and not slug.startswith("#"):
                            txt = _clean_text(a.css("::text").getall())
                            if txt and not txt.startswith("#"):
                                href = c_href
                                listing_title = txt
                                break

            # 4. Fallback for legacy markup
            if not href:
                c_href = card.css("h2.complaint-title a::attr(href)").get()
                if c_href and c_href.startswith(f"/{self.company}/") and not c_href.startswith("/uye/"):
                    href = c_href
                    listing_title = _clean_text(card.css("h2.complaint-title a::text").getall())

            if not href:
                continue

            if not listing_title:
                t_parts = card.css("h3 ::text, h2 ::text").getall()
                if t_parts:
                    listing_title = _clean_text(t_parts)
                else:
                    links = card.css("a")
                    first_link = links[0] if links else None
                    listing_title = _normalized_text(first_link) if first_link is not None else None

            complaint_url = urljoin("https://www.sikayetvar.com", href)
            normalized_card_text = _clean_text(card.css("::text").getall()) or ""
            listing_resolved = "Çözüldü" in normalized_card_text

            card_date_text = card.css("span[class*='text-zinc-500']::text, time::attr(datetime), time::text, .post-time::text, [class*='date']::text, [class*='time']::text").get()
            listing_date = parse_datetime(card_date_text) if card_date_text else None
            if listing_date is None:
                listing_date = parse_datetime(normalized_card_text)

            if listing_date is not None:
                parsed_dates.append(listing_date.date())
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
        if self.start_date and parsed_dates and max(parsed_dates) < self.start_date:
            self.logger.info(
                "Page %s: sayfadaki bütün şikâyet tarihleri (%s) başlangıç tarihinden (%s) eski. Kronolojik sıralama nedeniyle tarama durduruluyor.",
                page_num,
                max(parsed_dates),
                self.start_date,
            )
            return

        if self.max_pages and page_num >= self.start_page + self.max_pages - 1:
            return
        yield self._listing_request(page_num + 1)

    def parse_complaint(self, response):
        if response.status in (403, 429):
            self.logger.warning("Şikâyet detayına erişilemedi (HTTP %s): %s", response.status, response.url)
            return

        # 1. Try structured data first (JSON-LD DiscussionForumPosting)
        structured_title = None
        structured_date = None
        structured_response_text = None
        structured_response_date = None

        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict):
                me = parsed.get("mainEntity")
                if isinstance(me, dict):
                    structured_title = me.get("headline") or structured_title
                    raw_date = me.get("dateCreated") or me.get("datePublished")
                    if raw_date and not structured_date:
                        structured_date = parse_datetime(raw_date)

                    comments = me.get("comment", [])
                    if isinstance(comments, list):
                        for c in comments:
                            if isinstance(c, dict):
                                author = c.get("author", {})
                                author_type = author.get("@type") if isinstance(author, dict) else ""
                                author_name = (author.get("name") if isinstance(author, dict) else str(author or "")).lower()
                                c_text = c.get("text", "").strip()
                                c_date = parse_datetime(c.get("datePublished"))
                                if author_type == "Organization" or (self.company and self.company.lower() in author_name) or "müşteri hizmetleri" in author_name or "değerli müşterimiz" in c_text.lower():
                                    if not structured_response_text and c_text:
                                        structured_response_text = c_text
                                        structured_response_date = c_date

        parsed_date = structured_date
        if parsed_date is None:
            date_text = (
                response.css("span[class*='text-zinc-500']::text").get()
                or response.css("div.post-time div::text").get()
                or response.css("time::attr(datetime)").get()
                or response.css("time::text").get()
            )
            parsed_date = parse_sikayetvar_date(date_text) if date_text else None
        if parsed_date is None:
            parsed_date = parse_datetime(response.meta.get("listing_date"))
        if parsed_date and not self._in_requested_range(parsed_date):
            self.logger.debug("Skipping complaint outside requested date range: %s", response.url)
            return

        title_parts = response.css("h1.complaint-detail-title ::text").getall() or response.css("h1 ::text").getall()
        title = structured_title or _clean_text(title_parts) or response.meta.get("listing_title")
        resolved = bool(response.meta.get("listing_resolved"))

        # Extract the company answer
        company_response_text, company_response_date = _event_from_containers(response, RESPONSE_CONTAINER_SELECTORS)
        if not company_response_text and structured_response_text:
            company_response_text = structured_response_text
            company_response_date = structured_response_date
        elif not company_response_date and structured_response_date:
            company_response_date = structured_response_date

        response_hours = elapsed_hours(parsed_date, company_response_date)
        if company_response_date is not None and response_hours is None:
            company_response_date = None

        detail_text = _extract_complaint_text(response)
        listing_excerpt = response.meta.get("listing_excerpt")
        complaint_text = sanitize_complaint_body(detail_text, company_response_text)
        if not complaint_text:
            complaint_text = sanitize_complaint_body(listing_excerpt)
        complaint_text = complaint_text or None

        if not complaint_text:
            self.logger.warning(
                "Şikâyet gövdesi alınamadı; SEO/firma yanıtı analiz verisi olarak kaydedilmedi: %s",
                response.url,
            )

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
