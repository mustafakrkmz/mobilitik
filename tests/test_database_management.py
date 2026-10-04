import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox

import mobilitik.desktop.app as app_module
from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.analysis.sentiment import ANALYZER_VERSION, DEFAULT_MODEL_ID
from mobilitik.desktop.data import ComplaintRepository


def _seed(db_path: Path):
    repo = ComplaintRepository(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO complaints (
                id, company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, response_hours, listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1, "istikbal", "https://example.test/ist1", "2026-09-28 10:00:00",
                    "Teslimat gecikti", "Teslimat yapıldı ancak geç geldi.",
                    0, 1, 24.0, 1, "2026-09-28T11:00:00",
                ),
                (
                    2, "istikbal", "https://example.test/ist2", "2026-09-28 11:00:00",
                    "Kumaş sorunu", "Kumaş dikişi açıldı.",
                    1, 1, 6.0, 1, "2026-09-28T12:00:00",
                ),
                (
                    3, "bellona", "https://example.test/bel1", "2026-09-28 12:00:00",
                    "Yatak gıcırdıyor", "Yatak baza kırık geldi.",
                    0, 0, None, 1, "2026-09-28T13:00:00",
                ),
            ],
        )

    store = SentimentStore(db_path)
    store.upsert_sentiment(
        1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
        label="negative", confidence=0.95, negative=0.92, neutral=0.05, positive=0.03,
    )
    store.upsert_sentiment(
        3, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h3",
        label="negative", confidence=0.88, negative=0.85, neutral=0.10, positive=0.05,
    )
    store.replace_aspects(
        1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
        [{"category": "Teslimat / Lojistik", "sentence_count": 1, "negative": 0.90, "neutral": 0.05, "positive": 0.05}],
    )
    return repo


def test_database_stats_reports_correct_metrics(tmp_path):
    db_path = tmp_path / "test_stats.db"
    repo = _seed(db_path)

    stats = repo.database_stats()
    assert stats["db_path"] == str(db_path)
    assert stats["file_size_bytes"] > 0
    assert stats["total_complaints"] == 3
    assert stats["total_sentiments"] == 2

    comp_map = {c["company"]: c for c in stats["companies"]}
    assert "istikbal" in comp_map
    assert "bellona" in comp_map

    assert comp_map["istikbal"]["count"] == 2
    assert comp_map["istikbal"]["resolved"] == 1
    assert comp_map["istikbal"]["nlp_count"] == 1
    assert comp_map["istikbal"]["min_date"] == "2026-09-28 10:00:00"
    assert comp_map["istikbal"]["max_date"] == "2026-09-28 11:00:00"

    assert comp_map["bellona"]["count"] == 1
    assert comp_map["bellona"]["resolved"] == 0
    assert comp_map["bellona"]["nlp_count"] == 1


def test_delete_company_cascades_and_preserves_other_companies(tmp_path):
    db_path = tmp_path / "test_delete.db"
    repo = _seed(db_path)

    result = repo.delete_company("istikbal")
    assert result["deleted_complaints"] == 2
    assert result["deleted_sentiments"] == 1
    assert result["deleted_aspects"] == 1

    stats = repo.database_stats()
    assert stats["total_complaints"] == 1
    assert stats["total_sentiments"] == 1
    companies = [c["company"] for c in stats["companies"]]
    assert "istikbal" not in companies
    assert "bellona" in companies

    # Check complaints table directly
    with sqlite3.connect(db_path) as conn:
        complaints = conn.execute("SELECT id, company FROM complaints").fetchall()
        assert len(complaints) == 1
        assert complaints[0][1] == "bellona"

        sentiments = conn.execute("SELECT complaint_id FROM sentiment_results").fetchall()
        assert len(sentiments) == 1
        assert sentiments[0][0] == 3


def test_reset_database_wipes_all_data(tmp_path):
    db_path = tmp_path / "test_reset.db"
    repo = _seed(db_path)

    result = repo.reset_database()
    assert result["deleted_complaints"] == 3
    assert result["deleted_sentiments"] == 2
    assert result["deleted_aspects"] == 1

    stats = repo.database_stats()
    assert stats["total_complaints"] == 0
    assert stats["total_sentiments"] == 0
    assert stats["companies"] == []

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sentiment_results").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM aspect_sentiment").fetchone()[0] == 0


def test_vacuum_database_executes_successfully(tmp_path):
    db_path = tmp_path / "test_vacuum.db"
    repo = _seed(db_path)
    repo.vacuum()
    assert db_path.exists()
    assert db_path.stat().st_size > 0


def test_database_tab_ui_integration_and_actions(monkeypatch, tmp_path):
    db_path = tmp_path / "test_ui.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    app = QApplication.instance() or QApplication([])
    window = app_module.MainWindow()
    try:
        window.refresh_database_tab()
        app.processEvents()

        # Check UI cards
        assert window.db_complaints_card[1].text() == "3"
        assert window.db_sentiment_card[1].text() == "2"
        assert window.db_companies_card[1].text() == "2"

        # Check table population
        assert window.db_company_table.rowCount() == 2
        comps = {window.db_company_table.item(r, 0).text() for r in range(2)}
        assert "istikbal" in comps
        assert "bellona" in comps

        # Test deleting a company via UI action with confirmation mocked
        monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

        window.db_company_combo.setCurrentText("istikbal")
        window._delete_selected_company_action()
        app.processEvents()

        assert window.db_complaints_card[1].text() == "1"
        assert window.db_companies_card[1].text() == "1"
        assert window.db_company_table.rowCount() == 1
        assert window.db_company_table.item(0, 0).text() == "bellona"

        # Test resetting database via UI action with confirmation mocked
        monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Yes)
        window._reset_database_action()
        app.processEvents()

        assert window.db_complaints_card[1].text() == "0"
        assert window.db_sentiment_card[1].text() == "0"
        assert window.db_companies_card[1].text() == "0"
        assert window.db_company_table.rowCount() == 0
    finally:
        window.close()
        app.processEvents()
