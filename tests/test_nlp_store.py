import sqlite3

from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.desktop.data import ComplaintRepository


MODEL = "test/model"
VERSION = "test-v1"


def _seed(db_path):
    ComplaintRepository(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, response_hours, listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("istikbal", "https://x/1", "2026-01-01 10:00:00", "Teslimat", "Gecikti", 0, 1, 24.0, 1, "2026-01-01T11:00:00"),
                ("istikbal", "https://x/2", "2026-02-01 10:00:00", "Montaj", "Hatalı", 1, 1, 6.0, 1, "2026-02-01T11:00:00"),
                ("bellona", "https://x/3", "2026-02-01 10:00:00", "Başlık", "Metin", 0, 0, None, 1, "2026-02-01T11:00:00"),
            ],
        )


def test_sentiment_cache_upsert_and_filter(tmp_path):
    db = tmp_path / "nlp.db"
    _seed(db)
    store = SentimentStore(db)

    store.upsert_sentiment(
        1, MODEL, VERSION, "hash1",
        label="negative", confidence=0.8, negative=0.8, neutral=0.15, positive=0.05,
    )
    store.upsert_sentiment(
        2, MODEL, VERSION, "hash2",
        label="neutral", confidence=0.6, negative=0.2, neutral=0.6, positive=0.2,
    )
    assert store.cached_hash(1, MODEL, VERSION) == "hash1"

    rows = store.complaint_results(
        model_id=MODEL,
        analyzer_version=VERSION,
        company="istikbal",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    assert len(rows) == 2
    counts = store.counts(
        model_id=MODEL,
        analyzer_version=VERSION,
        company="istikbal",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    assert counts["total"] == 2
    assert counts["negative"] == 1
    assert counts["neutral"] == 1
    assert counts["positive"] == 0
    assert counts["mean_negative"] == 0.5

    # Same complaint/model/version updates rather than duplicates.
    store.upsert_sentiment(
        1, MODEL, VERSION, "hash1-new",
        label="positive", confidence=0.7, negative=0.1, neutral=0.2, positive=0.7,
    )
    assert store.cached_hash(1, MODEL, VERSION) == "hash1-new"
    assert len(store.complaint_results(model_id=MODEL, analyzer_version=VERSION, company="istikbal")) == 2


def test_aspect_replace_and_cumulative_query(tmp_path):
    db = tmp_path / "nlp.db"
    _seed(db)
    store = SentimentStore(db)

    store.replace_aspects(
        1,
        MODEL,
        VERSION,
        "h1",
        [
            {
                "category": "Teslimat / Lojistik",
                "sentence_count": 2,
                "negative": 0.9,
                "neutral": 0.08,
                "positive": 0.02,
            }
        ],
    )
    store.replace_aspects(
        2,
        MODEL,
        VERSION,
        "h2",
        [
            {
                "category": "Montaj / Servis",
                "sentence_count": 1,
                "negative": 0.6,
                "neutral": 0.3,
                "positive": 0.1,
            }
        ],
    )

    assert store.aspect_cached_hash(1, MODEL, VERSION) == "h1"
    rows = {row["category"]: row for row in store.aspect_results(
        model_id=MODEL,
        analyzer_version=VERSION,
        company="istikbal",
    )}
    assert rows["Teslimat / Lojistik"]["complaints"] == 1
    assert rows["Teslimat / Lojistik"]["mean_negative"] == 0.9
    assert rows["Teslimat / Lojistik"]["high_negative_rate"] == 1.0
    assert rows["Teslimat / Lojistik"]["unresolved_rate"] == 1.0
    assert rows["Montaj / Servis"]["unresolved_rate"] == 0.0

    # Replacing aspects clears stale category rows for the same complaint/version.
    store.replace_aspects(
        1,
        MODEL,
        VERSION,
        "h1b",
        [
            {
                "category": "İade / Ücret",
                "sentence_count": 1,
                "negative": 0.7,
                "neutral": 0.2,
                "positive": 0.1,
            }
        ],
    )
    rows = {row["category"]: row for row in store.aspect_results(
        model_id=MODEL,
        analyzer_version=VERSION,
        company="istikbal",
    )}
    assert "Teslimat / Lojistik" not in rows
    assert "İade / Ücret" in rows
