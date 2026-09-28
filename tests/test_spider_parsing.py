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


def test_parse_listing_extracts_detail_url_and_resolved_state():
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
    detail = requests[0]
    assert detail.url == "https://www.sikayetvar.com/istikbal/ornek-sikayet"
    assert detail.meta["listing_page"] == 1
    assert detail.meta["listing_resolved"] is True


def test_parse_complaint_extracts_core_fields_and_company_response():
    spider = ComplaintSpider(company="istikbal")
    html = """
    <html><body>
      <div class="post-time"><div>31 Aralık 2025 18:24</div></div>
      <h1 class="complaint-detail-title">Teslimat gecikmesi</h1>
      <div class="complaint-detail-description">Siparişim teslim edilmedi.</div>
      <div class="brand-answer">Firma tarafından dönüş yapıldı.</div>
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
