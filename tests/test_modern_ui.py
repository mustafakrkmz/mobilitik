import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

import mobilitik.desktop.app as app_module
from mobilitik.desktop.data import ComplaintRepository
from mobilitik.desktop.modern_ui import ModernMainWindow


def _seed(db_path):
    ComplaintRepository(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, response_hours, resolution_hours,
                listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("bellona", "https://example.test/1", "2026-09-28 10:00:00",
                 "Verona koltuk takımı", "Verona koltuk takımı kumaşı açıldı ve servis gelmedi.",
                 0, 1, 8.0, None, 1, "2026-09-28T10:01:00"),
                ("bellona", "https://example.test/2", "2026-09-29 10:00:00",
                 "Verona koltuk takımı", "Verona koltuk takımı teslimatı gecikti.",
                 1, 1, 4.0, 24.0, 1, "2026-09-29T10:01:00"),
                ("bellona", "https://example.test/3", "2026-09-29 11:00:00",
                 "Mavenna koltuk takımı", "Mavenna koltuk takımı dikişi açıldı.",
                 0, 0, None, None, 1, "2026-09-29T11:01:00"),
            ],
        )


def test_modern_dashboard_and_context_analysis(monkeypatch, tmp_path):
    db_path = tmp_path / "modern.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        window.company_combo.setCurrentText("bellona")
        window.start_date.setDate(QDate(2026, 9, 28))
        window.end_date.setDate(QDate(2026, 9, 29))
        window.refresh_analysis()
        app.processEvents()

        assert window.tabs.indexOf(window.dashboard_tab) == 0
        assert window.dashboard_cards["Toplam Şikâyet"][1].text() == "3"
        assert window.dashboard_cards["Çözülen"][2].text() == "%33.3"
        assert window.dashboard_category_table.rowCount() > 0
        assert window.dashboard_category_chart.data
        assert window.dashboard_trend_chart.data

        window.context_anchor.setCurrentText("koltuk takımı")
        window.context_direction.setCurrentIndex(0)
        window.context_window.setValue(1)
        window.refresh_context_analysis()
        app.processEvents()

        assert window.context_cards["Çapayı İçeren"][1].text() == "3"
        contexts = {
            window.context_table.item(row, 0).text(): window.context_table.item(row, 2).text()
            for row in range(window.context_table.rowCount())
        }
        assert contexts["verona"] == "2"
        assert contexts["mavenna"] == "1"
        assert window.context_chart.data

        verona_row = next(
            row for row in range(window.context_table.rowCount())
            if window.context_table.item(row, 0).text() == "verona"
        )
        window._open_context_matches(verona_row, 0)
        assert window._open_drilldown_dialogs
        assert len(window._open_drilldown_dialogs[-1].records) == 2
    finally:
        window.close()
        app.processEvents()


def test_modern_benchmark_tab(monkeypatch, tmp_path):
    db_path = tmp_path / "modern_benchmark.db"
    _seed(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO complaints (company, complaint_url, complaint_date, title, complaint_text, resolved, company_responded, scraped_at)
            VALUES ('istikbal', 'http://ex.test/ist1', '2026-09-28', 'T', 'M', 1, 1, '2026-09-28')
            """
        )
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        assert hasattr(window, "benchmark_tab")
        assert window.tabs.indexOf(window.benchmark_tab) >= 0
        window.benchmark_c1.setCurrentText("bellona")
        window.benchmark_c2.setCurrentText("istikbal")
        window._run_benchmark()
        app.processEvents()

        assert window.benchmark_table.rowCount() == 5
        assert window.benchmark_table.item(0, 0).text() == "Toplam Şikâyet"
        assert window.benchmark_table.item(0, 1).text() == "3"
        assert window.benchmark_table.item(0, 2).text() == "1"
    finally:
        window.close()
        app.processEvents()


def test_database_tab_is_at_the_end(monkeypatch, tmp_path):
    db_path = tmp_path / "modern_db_pos.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        assert hasattr(window, "database_tab")
        total_tabs = window.tabs.count()
        db_index = window.tabs.indexOf(window.database_tab)
        # Database management must be the very last tab
        assert db_index == total_tabs - 1
        assert window.tabs.tabText(db_index) == "Veritabanı Yönetimi"
    finally:
        window.close()
        app.processEvents()


def test_modern_verb_analysis_sentence_listing(monkeypatch, tmp_path):
    db_path = tmp_path / "modern_verb.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        window.company_combo.setCurrentText("bellona")
        window.start_date.setDate(QDate(2026, 9, 28))
        window.end_date.setDate(QDate(2026, 9, 29))
        window.refresh_analysis()
        app.processEvents()

        # Check modern verb sentence table
        assert hasattr(window, "verb_sentence_table")
        assert window.verb_sentence_table.rowCount() > 0
        assert window.verb_root_filter_combo.count() > 1
        assert window.verb_cards["Toplam Cümle"][1].text() != "0"

        # Check sentences contain registered roots (e.g. aç, gel, git)
        roots_in_table = {
            window.verb_sentence_table.item(r, 1).text()
            for r in range(window.verb_sentence_table.rowCount())
        }
        assert "aç" in roots_in_table or "gel" in roots_in_table

        # Test filtering by a root present in the data
        first_root = sorted(roots_in_table)[0]
        root_idx = window.verb_root_filter_combo.findData(first_root)
        if root_idx >= 0:
            window.verb_root_filter_combo.setCurrentIndex(root_idx)
            app.processEvents()
            assert window.verb_sentence_table.rowCount() > 0
            for r in range(window.verb_sentence_table.rowCount()):
                assert window.verb_sentence_table.item(r, 1).text() == first_root

        # Double click opens detail dialog
        dialog = window._open_verb_sentence_detail(0, 0)
        assert dialog is not None
        dialog.close()
    finally:
        window.close()
        app.processEvents()


def test_context_analysis_fullscreen_and_chart_proportions(monkeypatch, tmp_path):
    from PySide6.QtGui import QResizeEvent
    from PySide6.QtCore import QSize

    db_path = tmp_path / "modern_ctx_fs.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        window.company_combo.setCurrentText("bellona")
        window.start_date.setDate(QDate(2026, 9, 28))
        window.end_date.setDate(QDate(2026, 9, 29))
        window.refresh_analysis()
        app.processEvents()

        # Simulate resizing to fullscreen 1920x1080
        window.resize(1920, 1080)
        app.processEvents()

        chart = window.context_chart
        assert chart is not None
        # Chart height and styling
        chart.set_data([("verona", 2.0), ("mavenna", 1.0)])
        assert len(chart.data) == 2

        # Card heights should be compact and not vertically bloated
        for card in window.context_cards.values():
            assert card[0].maximumHeight() <= 80

        # Context table has row selection enabled
        from PySide6.QtWidgets import QTableWidget
        assert window.context_table.selectionBehavior() == QTableWidget.SelectRows
    finally:
        window.close()
        app.processEvents()


def test_modern_ui_fullscreen_and_compact_height_no_squish(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QScrollArea

    db_path = tmp_path / "modern_squish.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = ModernMainWindow()
    try:
        window.company_combo.setCurrentText("bellona")
        window.start_date.setDate(QDate(2026, 9, 28))
        window.end_date.setDate(QDate(2026, 9, 29))
        window.refresh_analysis()
        app.processEvents()

        # Check tabs use QScrollArea to prevent squishing
        assert isinstance(window.dashboard_tab, QScrollArea)
        assert isinstance(window.context_tab, QScrollArea)

        # Check minimum and maximum heights of dashboard cards
        for card_frame, val_lbl, det_lbl in window.dashboard_cards.values():
            assert card_frame.minimumHeight() >= 66
            assert card_frame.maximumHeight() <= 80

        # Check table minimum heights
        assert window.dashboard_category_table.minimumHeight() >= 180
        assert window.context_table.minimumHeight() >= 200

        # Check top metric cards minimum height
        assert window.total_card[0].minimumHeight() >= 60

        # Simulate small/scaled laptop screen (e.g. 1280x720)
        window.resize(1280, 720)
        app.processEvents()

        # Ensure cards have not collapsed
        for card_frame, _, _ in window.dashboard_cards.values():
            assert card_frame.minimumHeight() >= 66
            assert card_frame.sizePolicy().verticalPolicy().name.lower() in ("fixed", "preferred")
    finally:
        window.close()
        app.processEvents()

