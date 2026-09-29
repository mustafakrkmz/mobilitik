import json
import sqlite3

from scrapy import Request
from scrapy.http import HtmlResponse

from mobilitik.analysis.sentiment import complaint_text as nlp_complaint_text
from mobilitik.desktop.data import ComplaintRepository
from mobilitik.spiders.complaints import ComplaintSpider
from mobilitik.text_quality import (
    analysis_text,
    is_boilerplate_complaint_text,
    sanitize_complaint_body,
)


def _response(url: str, html: str, meta=None):
    request = Request(url=url, meta=meta or {})
    return HtmlResponse(
        url=url,
        request=request,
        body=html.encode("utf-8"),
        encoding="utf-8",
    )


def test_sikayetvar_seo_preview_is_not_consumer_text():
    seo = (
        "Bellona için yazılan 'Eksik Gelen Masa Parçası İçin Ek Ücret Talebi Haksız Ve Kabul Edilemez' "
        "şikayetini ve yorumlarını okumak ya da Bellona hakkında şikayet yazmak için tıklayın!"
    )
    assert is_boilerplate_complaint_text(seo) is True
    assert sanitize_complaint_body(seo) == ""
    assert analysis_text("Eksik gelen masa parçası", seo) == "Eksik gelen masa parçası"
    assert nlp_complaint_text("Eksik gelen masa parçası", seo) == "Eksik gelen masa parçası"


def test_real_consumer_text_is_kept():
    body = "Siparişimde masa ayağı eksik geldi ve eksik parça için benden yeniden ücret talep edildi."
    assert is_boilerplate_complaint_text(body) is False
    assert sanitize_complaint_body(body) == body


def test_company_response_tail_is_removed_from_consumer_text():
    complaint = (
        "Masa takımım eksik teslim edildi. Eksik parçanın ücretsiz tamamlanmasını talep ediyorum."
    )
    response = (
        "Değerli Müşterimiz, Öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz. "
        "Talebiniz ilgili birimlere iletilmiş olup, Tüketici Hizmetleri Yetkilimiz sizinle irtibata geçecektir. "
        "Saygılarımızla, Bellona Müşteri Hizmetleri"
    )
    mixed = f"{complaint} {response}"
    assert sanitize_complaint_body(mixed, response) == complaint
    assert "değerli müşterimiz" not in analysis_text("Eksik masa parçası", mixed).lower()


def test_detail_seo_description_falls_back_to_real_listing_excerpt():
    spider = ComplaintSpider(company="bellona")
    title = "Eksik Gelen Masa Parçası İçin Ek Ücret Talebi Haksız Ve Kabul Edilemez"
    seo = (
        f"Bellona için yazılan '{title}' şikayetini ve yorumlarını okumak ya da "
        "Bellona hakkında şikayet yazmak için tıklayın!"
    )
    listing_excerpt = (
        "Bellona'dan aldığım masa takımında eksik parça çıktı. Eksik parçanın tamamlanması için "
        "benden ek ücret istenmesini kabul etmiyorum."
    )
    html = f"""
    <html><body>
      <h1>{title}</h1>
      <script type="application/ld+json">{json.dumps({"description": seo}, ensure_ascii=False)}</script>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/bellona/ornek-sikayet",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/bellona/ornek-sikayet",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": title,
            "listing_date": "2026-09-29 16:19:00",
            "listing_excerpt": listing_excerpt,
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["complaint_text"] == listing_excerpt
    assert "yorumlarını okumak" not in item["complaint_text"]


def test_generic_long_detail_paragraph_beats_seo_description():
    spider = ComplaintSpider(company="bellona")
    real_body = (
        "Bellona mağazasından aldığım yatak kısa süre içinde çökmeye başladı. Servis kaydı oluşturdum "
        "ancak iki ziyaret sonrasında da kalıcı bir çözüm sunulmadı ve sorun devam ediyor."
    )
    seo = (
        "Bellona için yazılan 'Yatak Sorunu' şikayetini ve yorumlarını okumak ya da "
        "Bellona hakkında şikayet yazmak için tıklayın!"
    )
    html = f"""
    <html><body><main>
      <h1>Yatak Sorunu</h1>
      <p>{real_body}</p>
      <script type="application/ld+json">{json.dumps({"description": seo}, ensure_ascii=False)}</script>
    </main></body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/bellona/yatak-sorunu",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/bellona/yatak-sorunu",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": "Yatak Sorunu",
            "listing_date": "2026-09-29 15:03:00",
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["complaint_text"] == real_body


def test_spider_separates_company_answer_from_broad_detail_container():
    spider = ComplaintSpider(company="bellona")
    complaint = (
        "Siparişimdeki masa parçası eksik geldi. Parçanın ücretsiz gönderilmesini ve mağduriyetimin giderilmesini istiyorum."
    )
    answer = (
        "Değerli Müşterimiz, Öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz. "
        "Talebiniz ilgili birimlere iletilmiş olup, Tüketici Hizmetleri Yetkilimiz sizinle irtibata geçecektir. "
        "Saygılarımızla, Bellona Müşteri Hizmetleri"
    )
    html = f"""
    <html><body>
      <div class="post-time"><div>29 Eylül 2026 16:19</div></div>
      <h1 class="complaint-detail-title">Eksik Masa Parçası</h1>
      <div class="complaint-detail-description">
        <p>{complaint}</p>
        <div class="company-response"><time datetime="2026-09-29T16:30:00">29 Eylül 16:30</time>{answer}</div>
      </div>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/bellona/eksik-masa-parcasi",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/bellona/eksik-masa-parcasi",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": "Eksik Masa Parçası",
            "listing_date": "2026-09-29 16:19:00",
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["complaint_text"] == complaint
    assert "değerli müşterimiz" not in item["complaint_text"].lower()
    assert item["company_responded"] is True
    assert "Değerli Müşterimiz" in item["company_response_text"]


def test_company_answer_only_detail_falls_back_to_listing_excerpt():
    spider = ComplaintSpider(company="bellona")
    listing_excerpt = "Koltuk takımımın kumaşı kısa sürede deforme oldu ve değişim talebime yanıt alamadım."
    answer = (
        "Değerli Müşterimiz, Öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz. "
        "Talebiniz ilgili birimlere iletilmiş olup, Tüketici Hizmetleri Yetkilimiz sizinle irtibata geçecektir."
    )
    html = f"""
    <html><body>
      <h1>Kumaş Sorunu</h1>
      <div class="complaint-detail-description company-response">{answer}</div>
    </body></html>
    """
    response = _response(
        "https://www.sikayetvar.com/bellona/kumas-sorunu",
        html,
        {
            "ref_url": "https://www.sikayetvar.com/bellona/kumas-sorunu",
            "listing_page": 1,
            "listing_resolved": False,
            "listing_title": "Kumaş Sorunu",
            "listing_date": "2026-09-29 15:00:00",
            "listing_excerpt": listing_excerpt,
        },
    )
    item = list(spider.parse_complaint(response))[0]
    assert item["complaint_text"] == listing_excerpt


def test_repository_scrubs_legacy_seo_preview_on_open(tmp_path):
    db_path = tmp_path / "legacy.db"
    ComplaintRepository(db_path)
    seo = (
        "Bellona için yazılan 'Başlık' şikayetini ve yorumlarını okumak ya da "
        "Bellona hakkında şikayet yazmak için tıklayın!"
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, scraped_at
            ) VALUES (?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (
                "bellona",
                "https://example.test/legacy",
                "2026-09-29 10:00:00",
                "Başlık",
                seo,
                "2026-09-29T10:01:00",
            ),
        )

    repo = ComplaintRepository(db_path)
    rows = repo.all_complaints()
    assert len(rows) == 1
    assert rows[0]["complaint_text"] is None


def test_repository_repairs_mixed_company_response_and_invalidates_nlp_cache(tmp_path):
    db_path = tmp_path / "mixed.db"
    ComplaintRepository(db_path)
    complaint = "Teslim edilen konsolun kapağı kırık çıktı ve değişim istiyorum."
    answer = (
        "Değerli Müşterimiz, Öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz. "
        "Talebiniz ilgili birimlere iletilmiş olup, Tüketici Hizmetleri Yetkilimiz sizinle irtibata geçecektir."
    )
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, company_response_text, scraped_at
            ) VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (
                "bellona",
                "https://example.test/mixed",
                "2026-09-29 10:00:00",
                "Kırık Konsol",
                f"{complaint} {answer}",
                answer,
                "2026-09-29T10:01:00",
            ),
        )
        complaint_id = cur.lastrowid
        conn.execute(
            "CREATE TABLE sentiment_results (complaint_id INTEGER, model_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE aspect_sentiment (complaint_id INTEGER, category TEXT)"
        )
        conn.execute("INSERT INTO sentiment_results VALUES (?, 'old-model')", (complaint_id,))
        conn.execute("INSERT INTO aspect_sentiment VALUES (?, 'Teslimat')", (complaint_id,))

    repo = ComplaintRepository(db_path)
    rows = repo.all_complaints()
    assert rows[0]["complaint_text"] == complaint
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sentiment_results").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM aspect_sentiment").fetchone()[0] == 0
