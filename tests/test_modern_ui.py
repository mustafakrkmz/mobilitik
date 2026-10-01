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
