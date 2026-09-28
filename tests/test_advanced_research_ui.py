import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

import mobilitik.desktop.app as app_module
import mobilitik.desktop.advanced_ui as advanced_ui
from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.analysis.sentiment import ANALYZER_VERSION, DEFAULT_MODEL_ID
from mobilitik.desktop.data import ComplaintRepository


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
                (
                    "istikbal", "https://example.test/a", "2026-09-28 10:00:00",
                    "Teslimat gecikti", "Teslimat yapıldı ancak ürün geç getirildi ve servis geliyor.",
                    0, 1, 24.0, 1, "2026-09-28T11:00:00",
                ),
                (
                    "istikbal", "https://example.test/b", "2026-09-28 11:00:00",
                    "Kumaş sorunu", "Kumaş değiştirildi fakat dikiş yeniden açıldı.",
                    1, 1, 6.0, 1, "2026-09-28T12:00:00",
                ),
                (
                    "istikbal", "https://example.test/c", "2026-09-28 12:00:00",
                    "Montaj yapılmadı", None,
                    0, 0, None, 1, "2026-09-28T13:00:00",
                ),
            ],
        )


def _make_window(monkeypatch, tmp_path):
    db_path = tmp_path / "advanced.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = advanced_ui.AdvancedMainWindow()
    window.company_combo.setCurrentText("istikbal")
    window.start_date.setDate(QDate(2026, 9, 28))
    window.end_date.setDate(QDate(2026, 9, 28))
    window.refresh_analysis()
    app.processEvents()
    return app, window, db_path


def test_null_complaint_text_uses_title_instead_of_missing_text_error(monkeypatch, tmp_path):
    app, window, _db = _make_window(monkeypatch, tmp_path)
    try:
        records = [r for r in window._analysis_records if r["complaint_text"] is None]
        assert records
        preview = window._tooltip_text(records[0])
        assert "Montaj yapılmadı" in preview
        assert "metni bulunamadı" not in preview.lower()
    finally:
        window.close()
        app.processEvents()


def test_word_and_category_drilldowns_open_matching_records(monkeypatch, tmp_path):
    app, window, _db = _make_window(monkeypatch, tmp_path)
    try:
        # Direct helper mirrors a double click on the word table.
        term_row = None
        for row in range(window.word_table.rowCount()):
            if window.word_table.item(row, 0).text() == "teslimat":
                term_row = row
                break
        assert term_row is not None
        window._open_word_matches(term_row, 0)
        dialog = window._open_drilldown_dialogs[-1]
        assert len(dialog.records) == 1
        assert "Teslimat" in dialog.records[0]["title"]

        category_row = None
        for row in range(window.category_table.rowCount()):
            if window.category_table.item(row, 0).text() == "Teslimat / Lojistik":
                category_row = row
                break
        assert category_row is not None
        window._open_category_matches(category_row, 1)
        category_dialog = window._open_drilldown_dialogs[-1]
        assert category_dialog.records
        assert any("Teslimat" in record["title"] for record in category_dialog.records)
    finally:
        window.close()
        app.processEvents()


def test_custom_passive_suffixes_are_visible_in_verb_table(monkeypatch, tmp_path):
    app, window, _db = _make_window(monkeypatch, tmp_path)
    try:
        window.verb_suffix_input.setText("ıyor; iyor; uyor; üyor; ıldı; ildi")
        window.refresh_verb_analysis()
        stems = {window.verb_table.item(row, 0).text() for row in range(window.verb_table.rowCount())}
        assert "yap" in stems
        assert "değiştir" in stems
        assert "gel" in stems
    finally:
        window.close()
        app.processEvents()


def test_detailed_nlp_statistics_render_from_cache(monkeypatch, tmp_path):
    app, window, db_path = _make_window(monkeypatch, tmp_path)
    try:
        store = SentimentStore(db_path)
        store.upsert_sentiment(
            1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
            label="negative", confidence=0.95, negative=0.92, neutral=0.05, positive=0.03,
        )
        store.upsert_sentiment(
            2, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h2",
            label="neutral", confidence=0.55, negative=0.30, neutral=0.55, positive=0.15,
        )
        store.replace_aspects(
            1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
            [{"category":"Teslimat / Lojistik","sentence_count":2,"negative":0.90,"neutral":0.07,"positive":0.03}],
        )
        store.replace_aspects(
            2, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h2",
            [{"category":"Üretim / Kalite","sentence_count":1,"negative":0.40,"neutral":0.45,"positive":0.15}],
        )
        window.refresh_nlp_cached_view()
        app.processEvents()

        assert window.nlp_inner_tabs.count() == 5
        labels = {window.nlp_detail_summary.item(row, 0).text(): window.nlp_detail_summary.item(row, 1).text()
                  for row in range(window.nlp_detail_summary.rowCount())}
        assert labels["Analiz edilen kayıt"] == "2"
        assert labels["Düşük model güveni (< %60)"] == "%50.0"
        assert window.nlp_aspect_detail_table.rowCount() == 2
        assert window.nlp_uncertain_table.rowCount() == 2
    finally:
        window.close()
        app.processEvents()
