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
        "company_response_date": None,
        "response_hours": None,
        "resolution_text": None,
        "resolution_date": None,
        "resolution_hours": None,
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
            "company_response_text": "İlgileniyoruz",
            "company_response_date": "2026-05-01 16:00:00",
            "response_hours": 6.0,
            "resolution_text": "Sorun çözüldü",
            "resolution_date": "2026-05-03 10:00:00",
            "resolution_hours": 48.0,
        }
    )
    pipeline.process_item(updated, None)
    pipeline.close_spider(None)

    with sqlite3.connect(tmp_path / "mobilitik.db") as conn:
        row = conn.execute(
            """
            SELECT COUNT(*), title, resolved, company_responded,
                   company_response_date, response_hours,
                   resolution_date, resolution_hours
            FROM complaints
            """
        ).fetchone()

    assert row == (
        1,
        "Güncel başlık",
        1,
        1,
        "2026-05-01 16:00:00",
        6.0,
        "2026-05-03 10:00:00",
        48.0,
    )


def test_pipeline_migrates_old_database(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "mobilitik.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                complaint_url TEXT NOT NULL UNIQUE,
                complaint_date TEXT,
                title TEXT,
                complaint_text TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                company_responded INTEGER NOT NULL DEFAULT 0,
                company_response_text TEXT,
                listing_page INTEGER,
                scraped_at TEXT NOT NULL
            )
            """
        )

    pipeline = SQLitePipeline()
    pipeline.open_spider(None)
    columns = {
        row[1]
        for row in pipeline.conn.execute("PRAGMA table_info(complaints)").fetchall()
    }
    pipeline.close_spider(None)

    assert {
        "company_response_date",
        "response_hours",
        "resolution_text",
        "resolution_date",
        "resolution_hours",
    }.issubset(columns)
