import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

import mobilitik.desktop.app as app_module
import mobilitik.desktop.enhanced_ui as enhanced_ui
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
                    "istikbal",
                    "https://example.test/delivery",
                    "2026-03-01 10:00:00",
                    "Teslimat gecikti",
                    "Teslimat tarihi sürekli ertelendi ve ürün hâlâ gelmiyor.",
                    0,
                    1,
                    24.0,
                    1,
                    "2026-03-01T11:00:00",
                ),
                (
                    "istikbal",
                    "https://example.test/quality",
                    "2026-04-01 10:00:00",
                    "Koltuk kumaşı deforme oldu",
                    "Kumaş dikişleri açıldı ve üretim hatası var.",
                    1,
                    1,
                    4.0,
                    1,
                    "2026-04-01T11:00:00",
                ),
            ],
        )


def _make_window(monkeypatch, tmp_path):
    db_path = tmp_path / "enhanced-ui.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = enhanced_ui.EnhancedMainWindow()
    window.company_combo.setCurrentText("istikbal")
    window.start_date.setDate(QDate(2026, 1, 1))
    window.end_date.setDate(QDate(2026, 12, 31))
    window.refresh_analysis()
    app.processEvents()
    return app, window


def test_explicit_hover_preview_calls_qtooltip(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    shown = []
    monkeypatch.setattr(
        enhanced_ui.QToolTip,
        "showText",
        lambda _pos, text, *_args, **_kwargs: shown.append(text),
    )
    try:
        item = window.table.item(0, 2)
        window._show_complaint_hover(item)
        assert shown
        assert "Kumaş dikişleri" in shown[-1]
        assert item.toolTip()
    finally:
        window.close()
        app.processEvents()


def test_distinctive_term_drills_down_to_matching_complaints(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        window.distinctive_category_combo.setCurrentText("Tümü")
        window._show_distinctive_matches_for_term("teslimat")
        assert window.distinctive_match_table.rowCount() == 1
        assert "Teslimat gecikti" in window.distinctive_match_table.item(0, 1).text()
        assert "Teslimat tarihi" in window.distinctive_match_table.item(0, 2).text()
        assert window.distinctive_match_table.cellWidget(0, 3).text().startswith("<a")

        window._show_distinctive_match_preview(0, 0)
        assert "ürün hâlâ gelmiyor" in window.distinctive_preview.toPlainText()

        window._show_distinctive_matches_for_term("kumaş")
        assert window.distinctive_match_table.rowCount() == 1
        assert "Koltuk kumaşı" in window.distinctive_match_table.item(0, 1).text()
    finally:
        window.close()
        app.processEvents()


def test_nlp_workspace_is_split_into_readable_subtabs(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        window.resize(900, 650)
        app.processEvents()
        assert window.nlp_inner_tabs.count() == 4
        assert [window.nlp_inner_tabs.tabText(i) for i in range(4)] == [
            "Çalıştırma",
            "Şikâyet Duyguları",
            "Gelişim Öncelikleri",
            "NLP Günlüğü",
        ]
        assert window.nlp_table.columnCount() == 7
        assert window.priority_table.columnCount() == 8
        assert window.nlp_status.wordWrap() is True
        assert window.frequency_weight.minimumWidth() >= 90
    finally:
        window.close()
        app.processEvents()
