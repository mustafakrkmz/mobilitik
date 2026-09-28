import sqlite3

from mobilitik.pipelines import SQLitePipeline


def test_sqlite_pipeline_inserts_and_updates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    pipeline = SQLitePipeline()
    pipeline.open_spider(None)

    item = {
        "company": "istikbal",
        "complaint_url": "https://example.test/c1",
        "complaint_date": "2026-05-01 10:00:00",
        "title": "İlk başlık",
        "complaint_text": "Teslimat gecikti",
        "resolved": False,
        "company_responded": False,
        "company_response_text": None,
        "listing_page": 1,
        "scraped_at": "2026-05-01T10:05:00",
    }
    assert pipeline.process_item(item, None) is item

    updated = dict(item)
    updated.update(
        {
            "title": "Güncel başlık",
            "resolved": True,
            "company_responded": True,
            "company_response_text": "Sorun çözüldü",
        }
    )
    pipeline.process_item(updated, None)
    pipeline.close_spider(None)

    with sqlite3.connect(tmp_path / "mobilitik.db") as conn:
        row = conn.execute(
            "SELECT COUNT(*), title, resolved, company_responded FROM complaints"
        ).fetchone()

    assert row == (1, "Güncel başlık", 1, 1)
