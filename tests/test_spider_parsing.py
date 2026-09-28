import asyncio

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


async def _collect_start(spider):
    return [item async for item in spider.start()]


def test_start_yields_initial_listing_request():
    spider = ComplaintSpider(company="istikbal", start_page=2)
    requests = asyncio.run(_collect_start(spider))
    assert len(requests) == 1
    request = requests[0]
    assert request.url == "https://www.sikayetvar.com/istikbal?page=2"
    assert request.meta["page_num"] == 2
    assert request.meta["playwright"] is True


def test_parse_listing_supports_current_markup():
    spider = ComplaintSpider(company="istikbal", max_pages=1)
    html = """
    <html><body>
      <article class="relative ga-c ga-v border-zinc-200 py-8 border-b">
        <a class="after:absolute after:inset-0 after:z-10"
           href="/istikbal/teslim-edilmeyen-koltuk">
          Teslim Edilmeyen Koltuk
        </a>
        <a href="/uye/ornek">Ayşe</a>
        <span>28 Eylül 16:55</span>
        <p>Ürünüm belirtilen tarihte teslim edilmedi.</p>
        <span>Çözüldü</span>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal?page=1",
        html,
        {"page_num": 1},
    )

    requests = list(spider.parse_listing(response))
    assert len(requests) == 1
    detail = requests[0]
    assert detail.url == "https://www.sikayetvar.com/istikbal/teslim-edilmeyen-koltuk"
    assert detail.meta["listing_page"] == 1
    assert detail.meta["listing_resolved"] is True
    assert detail.meta["listing_title"] == "Teslim Edilmeyen Koltuk"
    assert detail.meta["listing_date"] is not None


def test_parse_listing_keeps_legacy_markup_compatibility():
    spider = ComplaintSpider(company="istikbal", max_pages=1)
    html = """
    <html><body>
      <article class="card-v2 ga-v ga-c">
        <h2 class="complaint-title"><a href="/istikbal/ornek-sikayet">Başlık</a></h2>
        <span>Çözüldü</span>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal?page=1",
        html,
        {"page_num": 1},
    )
    requests = list(spider.parse_listing(response))
    assert len(requests) == 1
    assert requests[0].url == "https://www.sikayetvar.com/istikbal/ornek-sikayet"


def test_parse_complaint_extracts_core_fields_and_timing():
    spider = ComplaintSpider(company="istikbal")
    html = """
    <html><body>
      <div class="post-time"><div>31 Aralık 2025 18:24</div></div>
      <h1 class="complaint-detail-title">Teslimat gecikmesi</h1>
      <div class="complaint-detail-description">Siparişim teslim edilmedi.</div>
      <div class="brand-answer">
        <time datetime="2026-01-01T06:24:00">1 Ocak 2026 06:24</time>
        Firma tarafından dönüş yapıldı.
      </div>
      <div class="complaint-solution">
        <time datetime="2026-01-02T18:24:00">2 Ocak 2026 18:24</time>
        Sorunum çözüldü, teşekkür ederim.
      </div>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal/ornek-sikayet",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/ornek-sikayet",
            "listing_page": 3,
            "listing_resolved": True,
        },
    )

    items = list(spider.parse_complaint(response))
    assert len(items) == 1
    item = items[0]
    assert item["company"] == "istikbal"
    assert item["complaint_date"] == "2025-12-31 18:24:00"
    assert item["title"] == "Teslimat gecikmesi"
    assert item["complaint_text"] == "Siparişim teslim edilmedi."
    assert item["resolved"] is True
    assert item["company_responded"] is True
    assert "dönüş yapıldı" in item["company_response_text"]
    assert item["company_response_date"] == "2026-01-01 06:24:00"
    assert item["response_hours"] == 12.0
    assert item["resolution_date"] == "2026-01-02 18:24:00"
    assert item["resolution_hours"] == 48.0
    assert "teşekkür" in item["resolution_text"]


def test_detail_can_fall_back_to_listing_title_and_date():
    spider = ComplaintSpider(company="istikbal")
    html = "<html><body><div class='complaint-detail-description'>Metin burada.</div></body></html>"
    response = _response(
        "https://www.sikayetvar.com/istikbal/yeni-yapi",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/yeni-yapi",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": "Liste Başlığı",
            "listing_date": "2026-09-28 16:55:00",
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["title"] == "Liste Başlığı"
    assert item["complaint_date"] == "2026-09-28 16:55:00"
    assert item["complaint_text"] == "Metin burada."


def test_timing_is_left_empty_when_status_has_no_explicit_date():
    spider = ComplaintSpider(company="istikbal")
    html = """
    <html><body>
      <div class="post-time"><div>28 Eylül 12:00</div></div>
      <h1 class="complaint-detail-title">Servis sorunu</h1>
      <div class="complaint-detail-description">Servis gelmedi.</div>
      <div class="brand-answer">Firma yanıt verdi ancak tarih görünmüyor.</div>
      <div class="complaint-solution">Çözüldü</div>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal/tarihsiz",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/tarihsiz",
            "listing_page": 1,
            "listing_resolved": True,
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["company_responded"] is True
    assert item["response_hours"] is None
    assert item["resolution_hours"] is None
