import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

import mobilitik.desktop.app as app_module
from mobilitik.desktop.data import ComplaintRepository


def _seed(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, company_response_text,
                company_response_date, response_hours,
                resolution_text, resolution_date, resolution_hours,
                listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "istikbal",
                    "https://example.test/gui1",
                    "2026-03-01 10:00:00",
                    "Teslimat gecikti",
                    "Teslimat tarihi ertelendi, kargo gelmiyor ve süreç gecikiyor.",
                    1,
                    1,
                    "İlgileniyoruz",
                    "2026-03-01 16:00:00",
                    6.0,
                    "Sorun çözüldü",
                    "2026-03-03 10:00:00",
                    48.0,
                    1,
                    "2026-03-01T11:00:00",
                ),
                (
                    "istikbal",
                    "https://example.test/gui2",
                    "2026-04-01 10:00:00",
                    "Koltuk kumaşı deforme oldu",
                    "Kumaş dikişleri açıldı ve üretim hatası var.",
                    0,
                    1,
                    "Servis yönlendirildi",
                    "2026-04-01 22:00:00",
                    12.0,
                    None,
                    None,
                    None,
                    1,
                    "2026-04-01T11:00:00",
                ),
            ],
        )


def _make_window(monkeypatch, tmp_path):
    db_path = tmp_path / "gui.db"
    ComplaintRepository(db_path)
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    return app, app_module.MainWindow()


def test_main_window_runs_analysis_headlessly(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        window.company_combo.setCurrentText("https://www.sikayetvar.com/istikbal")
        window.start_date.setDate(QDate(2026, 1, 1))
        window.end_date.setDate(QDate(2026, 12, 31))
        window.refresh_analysis()
        app.processEvents()

        assert window.tabs.count() == 6
        assert window.total_card[1].text() == "2"
        assert window.resolved_card[1].text() == "%50.0"
        assert window.response_card[1].text() == "%100.0"
        assert window.response_time_card[1].text() == "9.0 sa"
        assert window.resolution_time_card[1].text() == "2.0 gün"
        assert window.table.columnCount() == 8
        assert window.table.rowCount() == 2
        assert window.category_table.columnCount() == 7
        assert window.category_table.item(0, 0).text() == "Tümü"
        assert window.category_table.rowCount() >= 3
        assert window.word_table.rowCount() > 0
        assert window.verb_table.rowCount() > 0
        assert window.distinctive_category_combo.itemText(0) == "Tümü"
        assert window.distinctive_table.rowCount() > 0
        assert window.category_editor.rowCount() > 0

        link = window.table.cellWidget(0, 7)
        assert isinstance(link, QLabel)
        assert link.openExternalLinks() is True
        assert "Şikâyeti aç" in link.text()
        assert link.toolTip()
        assert window.table.item(0, 2).toolTip()
    finally:
        window.close()
        app.processEvents()


def test_apply_filter_updates_complaint_list_and_category_filter(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        window.company_combo.setCurrentText("istikbal")
        window.start_date.setDate(QDate(2026, 3, 15))
        window.end_date.setDate(QDate(2026, 12, 31))
        window.refresh_analysis()
        app.processEvents()
        assert window.total_card[1].text() == "1"
        assert window.table.rowCount() == 1
        assert "Koltuk kumaşı" in window.table.item(0, 2).text()

        window.start_date.setDate(QDate(2026, 1, 1))
        window.refresh_analysis()
        window.complaint_category_combo.setCurrentText("Teslimat / Lojistik")
        app.processEvents()
        assert window.table.rowCount() == 1
        assert "Teslimat" in window.table.item(0, 2).text()
    finally:
        window.close()
        app.processEvents()


def test_verb_filter_reduces_visible_verb_rows(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        window.company_combo.setCurrentText("istikbal")
        window.start_date.setDate(QDate(2026, 1, 1))
        window.end_date.setDate(QDate(2026, 12, 31))
        window.refresh_analysis()
        assert window.verb_table.rowCount() >= 2
        window.verb_filter.setText("gelm")
        app.processEvents()
        assert window.verb_table.rowCount() == 1
        assert window.verb_table.item(0, 0).text() == "gelm"
    finally:
        window.close()
        app.processEvents()


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _FakeProcess:
    NotRunning = 0
    MergedChannels = 1

    def __init__(self, parent=None):
        self.parent = parent
        self.readyReadStandardOutput = _Signal()
        self.finished = _Signal()
        self.program = None
        self.arguments = None
        self.channel_mode = None
        self._state = self.NotRunning
        self.started = False
        self.terminated = False

    def setProgram(self, program):
        self.program = program

    def setArguments(self, arguments):
        self.arguments = list(arguments)

    def setProcessChannelMode(self, mode):
        self.channel_mode = mode

    def state(self):
        return self._state

    def start(self):
        self.started = True
        self._state = 1

    def terminate(self):
        self.terminated = True
        self._state = self.NotRunning

    def waitForFinished(self, _milliseconds):
        return True

    def kill(self):
        self._state = self.NotRunning


def test_main_window_builds_and_starts_scraper_process(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "QProcess", _FakeProcess)
    try:
        window.company_combo.setCurrentText("https://www.sikayetvar.com/cilek-mobilya")
        window.start_date.setDate(QDate(2026, 1, 1))
        window.end_date.setDate(QDate(2026, 9, 28))
        window.max_pages.setValue(2)
        window.start_scraping()

        assert isinstance(window.process, _FakeProcess)
        assert window.process.started is True
        assert "company=cilek-mobilya" in window.process.arguments
        assert "max_pages=2" in window.process.arguments
        assert window.start_button.isEnabled() is False
        assert window.stop_button.isEnabled() is True

        window.stop_scraping()
        assert window.process.terminated is True
    finally:
        window.close()
        app.processEvents()
