import asyncio
import json

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


def test_listing_date_filter_skips_only_out_of_range_cards():
    spider = ComplaintSpider(
        company="istikbal", start_date="2026-09-28", end_date="2026-09-28", max_pages=1
    )
    html = """
    <html><body>
      <article class="relative ga-c ga-v">
        <a href="/istikbal/bugunku-sikayet">Bugünkü şikâyet</a>
        <span>28 Eylül 16:55</span>
      </article>
      <article class="relative ga-c ga-v">
        <a href="/istikbal/dunku-sikayet">Dünkü şikâyet</a>
        <span>27 Eylül 16:55</span>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal?page=1", html, {"page_num": 1}
    )
    requests = list(spider.parse_listing(response))
    assert len(requests) == 1
    assert requests[0].url.endswith("/bugunku-sikayet")


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


def test_out_of_range_detail_is_skipped_without_closing_spider():
    spider = ComplaintSpider(
        company="istikbal", start_date="2026-09-28", end_date="2026-09-28"
    )
    html = """
    <html><body>
      <div class="post-time"><div>27 Eylül 2026 18:24</div></div>
      <h1 class="complaint-detail-title">Eski şikâyet</h1>
      <div class="complaint-detail-description">Bu kayıt aralık dışında.</div>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal/eski-sikayet",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/eski-sikayet",
            "listing_page": 1,
            "listing_resolved": False,
        },
    )
    assert list(spider.parse_complaint(response)) == []


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


def test_listing_early_stopping_when_all_cards_older_than_start_date():
    spider = ComplaintSpider(
        company="istikbal", start_date="2026-10-01", max_pages=5
    )
    html = """
    <html><body>
      <article class="relative ga-c ga-v">
        <a href="/istikbal/eski-sikayet-1">Eski şikâyet 1</a>
        <span>20 Eylül 16:55</span>
      </article>
      <article class="relative ga-c ga-v">
        <a href="/istikbal/eski-sikayet-2">Eski şikâyet 2</a>
        <span>15 Eylül 12:00</span>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal?page=1", html, {"page_num": 1}
    )
    requests = list(spider.parse_listing(response))
    assert len(requests) == 0


def test_structured_discussion_forum_posting_extracts_full_text():
    spider = ComplaintSpider(company="istikbal")
    ld_data = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "mainEntity": {
            "@type": "DiscussionForumPosting",
            "headline": "Koltuk Takımı Kusurlu Geldi",
            "dateCreated": "2026-10-04T14:30:00+03:00",
            "text": "Birinci paragraf: Koltuk takımını 3 ay önce sipariş ettik ancak kumaşı yırtık teslim edildi.\n\nİkinci paragraf: Müşteri hizmetlerini defalarca aramamıza rağmen servis yönlendirilmedi ve mağdur edildik.",
            "comment": [
                {
                    "@type": "Comment",
                    "text": "Değerli Müşterimiz, Talebiniz kayıt altına alınmış olup inceleme başlatılmıştır.",
                    "datePublished": "2026-10-04T15:00:00+03:00",
                    "author": {
                        "@type": "Organization",
                        "name": "İstikbal Müşteri Hizmetleri",
                    },
                }
            ],
        },
    }
    html = f"""
    <html><body>
      <script type="application/ld+json">{json.dumps(ld_data, ensure_ascii=False)}</script>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal/koltuk-kusurlu",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/koltuk-kusurlu",
            "listing_page": 1,
            "listing_resolved": False,
        },
    )
    items = list(spider.parse_complaint(response))
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Koltuk Takımı Kusurlu Geldi"
    assert item["complaint_date"] == "2026-10-04 14:30:00"
    assert "Birinci paragraf" in item["complaint_text"]
    assert "İkinci paragraf" in item["complaint_text"]
    assert item["company_responded"] is True
    assert "Talebiniz kayıt altına alınmış" in item["company_response_text"]
    assert item["company_response_date"] == "2026-10-04 15:00:00"
    assert item["response_hours"] == 0.5


def test_all_article_paragraphs_preserves_multiple_paragraphs():
    spider = ComplaintSpider(company="istikbal")
    html = """
    <html><body>
      <article>
        <h1>Geciken Teslimat ve İlgisizlik</h1>
        <div class="mt-4 md:mt-5 font-normal">
          <p>İlk paragraf: Mağazadan aldığımız yemek odası takımı belirtilen tarihten 2 ay sonra geldi.</p>
          <p>İkinci paragraf: Gelen ürünlerin sandalyeleri eksikti ve masa tablasında derin çizikler mevcuttu.</p>
          <p>Üçüncü paragraf: Durumu derhal bildirmemize rağmen herhangi bir aksiyon alınmadı ve mağduriyetimiz giderilmedi.</p>
        </div>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal/geciken-teslimat",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/istikbal/geciken-teslimat",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": "Geciken Teslimat ve İlgisizlik",
            "listing_date": "2026-10-04 12:00:00",
        },
    )
    items = list(spider.parse_complaint(response))
    assert len(items) == 1
    text = items[0]["complaint_text"]
    assert "İlk paragraf" in text
    assert "İkinci paragraf" in text
    assert "Üçüncü paragraf" in text


def test_parse_listing_captures_tailwind_and_video_cards():
    spider = ComplaintSpider(company="istikbal", max_pages=1)
    html = """
    <html><body>
      <!-- Modern standard card with h3 a -->
      <article class="group relative isolate w-full py-6 md:py-8 border-b">
        <h3>
          <a href="/istikbal/standart-sikayet" title="Standart Şikâyet Başlığı">
            Standart Şikâyet Başlığı
          </a>
        </h3>
        <span class="text-zinc-500">4 Ekim 10:00</span>
        <p>Standart şikâyet açıklama metni burada.</p>
      </article>

      <!-- Video complaint card with a[title] -->
      <article class="group relative isolate w-full py-6 md:py-8 border-b">
        <a href="/istikbal/video-sikayet" title="Videolu Şikâyet Başlığı" class="font-semibold">
          Videolu Şikâyet Başlığı
        </a>
        <span class="text-zinc-500">4 Ekim 09:30</span>
        <p>Videolu şikâyet açıklama metni burada.</p>
      </article>

      <!-- Category tag link that should not be parsed as a complaint -->
      <article class="group relative isolate w-full py-6 md:py-8 border-b">
        <a href="/istikbal/koltuk-takimlari"># Koltuk Takımları</a>
      </article>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/istikbal?page=1",
        html,
        {"page_num": 1},
    )
    requests = list(spider.parse_listing(response))
    assert len(requests) == 2
    urls = [r.url for r in requests]
    assert "https://www.sikayetvar.com/istikbal/standart-sikayet" in urls
    assert "https://www.sikayetvar.com/istikbal/video-sikayet" in urls
    titles = [r.meta["listing_title"] for r in requests]
    assert "Standart Şikâyet Başlığı" in titles
    assert "Videolu Şikâyet Başlığı" in titles

