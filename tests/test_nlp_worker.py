import sqlite3

import mobilitik.nlp_worker as worker
from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.analysis.sentiment import ANALYZER_VERSION
from mobilitik.desktop.data import ComplaintRepository


MODEL = "fake/turkish-sentiment"


class FakeClassifier:
    def __init__(self):
        self.calls = 0

    def __call__(self, texts, **_kwargs):
        self.calls += 1
        result = []
        for text in texts:
            negative = 0.9 if any(word in text.casefold() for word in ("gecikti", "hatası", "gelmiyor")) else 0.2
            neutral = 0.08 if negative > 0.5 else 0.6
            positive = 1.0 - negative - neutral
            result.append([
                {"label": "Negative", "score": negative},
                {"label": "Neutral", "score": neutral},
                {"label": "Positive", "score": positive},
            ])
        return result


def _seed(db_path):
    ComplaintRepository(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "istikbal",
                "https://example.test/nlp-1",
                "2026-09-01 10:00:00",
                "Teslimat gecikti",
                "Teslimat gecikti. Montaj hatası var ve servis gelmiyor.",
                0,
                1,
                1,
                "2026-09-01T11:00:00",
            ),
        )


def test_worker_analyzes_and_then_uses_cache(monkeypatch, tmp_path):
    db = tmp_path / "worker.db"
    _seed(db)
    fake = FakeClassifier()
    monkeypatch.setattr(worker, "_load_classifier", lambda _model: fake)

    code = worker.run(
        db_path=str(db),
        company="https://www.sikayetvar.com/istikbal",
        start_date="2026-09-01",
        end_date="2026-09-30",
        model_id=MODEL,
    )
    assert code == 0
    assert fake.calls >= 1

    store = SentimentStore(db)
    rows = store.complaint_results(
        model_id=MODEL,
        analyzer_version=ANALYZER_VERSION,
        company="istikbal",
    )
    assert len(rows) == 1
    assert rows[0]["label"] == "negative"
    aspects = {row["category"] for row in store.aspect_results(
        model_id=MODEL,
        analyzer_version=ANALYZER_VERSION,
        company="istikbal",
    )}
    assert "Teslimat / Lojistik" in aspects
    assert "Montaj / Servis" in aspects

    # A fully cached second run must not even load the model.
    monkeypatch.setattr(worker, "_load_classifier", lambda _model: (_ for _ in ()).throw(AssertionError("model loaded")))
    code = worker.run(
        db_path=str(db),
        company="istikbal",
        start_date="2026-09-01",
        end_date="2026-09-30",
        model_id=MODEL,
    )
    assert code == 0


def test_predict_accepts_single_style_pipeline_output():
    class SingleStyle:
        def __call__(self, texts, **_kwargs):
            assert len(texts) == 1
            return [
                {"label": "Negative", "score": 0.1},
                {"label": "Neutral", "score": 0.2},
                {"label": "Positive", "score": 0.7},
            ]

    result = worker._predict(SingleStyle(), ["iyi"])
    assert len(result) == 1
    assert result[0].label == "positive"
