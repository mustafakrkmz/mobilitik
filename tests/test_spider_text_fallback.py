from scrapy import Request
from scrapy.http import HtmlResponse

from mobilitik.spiders.complaints import ComplaintSpider


def _response(url: str, html: str, meta=None):
    request = Request(url=url, meta=meta or {})
    return HtmlResponse(
        url=url,
        request=request,
        body=html.encode("utf-8"),
        encoding="utf-8",
    )


def test_listing_excerpt_is_passed_to_detail_and_used_as_fallback():
    spider = ComplaintSpider(
        company="istikbal",
        start_date="2026-09-28",
        end_date="2026-09-28",
        max_pages=1,
    )
    listing = _response(
        "https://www.sikayetvar.com/istikbal?page=1",
        """
        <html><body>
          <article class="ga-c ga-v">
            <a href="/istikbal/geciken-teslimat">Geciken Teslimat</a>
            <span>28 Eylül 18:20</span>
            <p>Yeni aldığım koltuk takımı söz verilen tarihte teslim edilmedi ve mağaza dönüş yapmıyor.</p>
          </article>
        </body></html>
        """,
        {"page_num": 1},
    )
    requests = list(spider.parse_listing(listing))
    assert len(requests) == 1
    assert "koltuk takımı" in requests[0].meta["listing_excerpt"]

    detail = _response(
        requests[0].url,
        "<html><body><h1>Geciken Teslimat</h1><div class='new-unknown-dom'>İçerik</div></body></html>",
        requests[0].meta,
    )
    item = list(spider.parse_complaint(detail))[0]
    assert "koltuk takımı" in item["complaint_text"]


def test_structured_data_can_supply_complaint_body():
    spider = ComplaintSpider(company="istikbal")
    detail = _response(
        "https://www.sikayetvar.com/istikbal/ornek",
        """
        <html><body>
          <h1>Örnek Başlık</h1>
          <script type="application/ld+json">
          {"@type":"Review","reviewBody":"Ürün teslim edildiğinde kapağı kırık çıktı ve servis iki haftadır gelmedi."}
          </script>
        </body></html>
        """,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/ornek",
            "listing_page": 1,
            "listing_resolved": False,
        },
    )
    item = list(spider.parse_complaint(detail))[0]
    assert "kapağı kırık" in item["complaint_text"]
