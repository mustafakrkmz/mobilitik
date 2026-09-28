import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

import mobilitik.desktop.app as app_module
import mobilitik.desktop.nlp_ui as nlp_ui
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
                    "istikbal", "https://example.test/a", "2026-03-01 10:00:00",
                    "Teslimat gecikti", "Teslimat tarihi ertelendi ve ürün gelmiyor.",
                    0, 1, 24.0, 1, "2026-03-01T11:00:00",
                ),
                (
                    "istikbal", "https://example.test/b", "2026-04-01 10:00:00",
                    "Koltuk kaliteli", "Koltuk güzel ama servis süreci normaldi.",
                    1, 1, 4.0, 1, "2026-04-01T11:00:00",
                ),
            ],
        )

    store = SentimentStore(db_path)
    store.upsert_sentiment(
        1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
        label="negative", confidence=0.9, negative=0.9, neutral=0.08, positive=0.02,
    )
    store.upsert_sentiment(
        2, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h2",
        label="positive", confidence=0.8, negative=0.1, neutral=0.1, positive=0.8,
    )
    store.replace_aspects(
        1, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h1",
        [{"category": "Teslimat / Lojistik", "sentence_count": 2, "negative": 0.9, "neutral": 0.08, "positive": 0.02}],
    )
    store.replace_aspects(
        2, DEFAULT_MODEL_ID, ANALYZER_VERSION, "h2",
        [{"category": "Montaj / Servis", "sentence_count": 1, "negative": 0.2, "neutral": 0.5, "positive": 0.3}],
    )


def _make_window(monkeypatch, tmp_path):
    db_path = tmp_path / "nlp-ui.db"
    _seed(db_path)
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app = QApplication.instance() or QApplication([])
    window = nlp_ui.NlpMainWindow()
    window.company_combo.setCurrentText("istikbal")
    window.start_date.setDate(QDate(2026, 1, 1))
    window.end_date.setDate(QDate(2026, 12, 31))
    window.refresh_nlp_cached_view()
    app.processEvents()
    return app, window


def test_nlp_tab_renders_cached_sentiment_and_priorities(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    try:
        assert window.tabs.count() == 7
        assert window.tabs.tabText(window.tabs.count() - 1) == "NLP / Duygu Analizi"
        assert window.nlp_total_card[1].text() == "2"
        assert window.nlp_negative_card[1].text() == "%50.0"
        assert window.nlp_positive_card[1].text() == "%50.0"
        assert window.nlp_intensity_card[1].text() == "%50.0"
        assert window.nlp_table.rowCount() == 2
        assert window.priority_table.rowCount() == 2
        categories = {window.priority_table.item(row, 0).text() for row in range(window.priority_table.rowCount())}
        assert "Teslimat / Lojistik" in categories
        assert "Montaj / Servis" in categories

        # Weight changes recalculate from cached data only; no model process is started.
        window.frequency_weight.setValue(100)
        window.negativity_weight.setValue(0)
        window.unresolved_weight.setValue(0)
        window.refresh_nlp_cached_view()
        assert window.priority_table.rowCount() == 2
        assert window.nlp_process is None
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
        self.arguments = []
        self._state = self.NotRunning
        self.output = b""
        self.terminated = False

    def setProgram(self, value):
        self.program = value

    def setArguments(self, value):
        self.arguments = list(value)

    def setProcessChannelMode(self, _value):
        pass

    def state(self):
        return self._state

    def start(self):
        self._state = 1

    def terminate(self):
        self.terminated = True
        self._state = self.NotRunning

    def waitForFinished(self, _ms):
        return True

    def kill(self):
        self._state = self.NotRunning

    def readAllStandardOutput(self):
        data = self.output
        self.output = b""
        return data


def test_nlp_start_uses_selected_root_url_and_is_opt_in(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    monkeypatch.setattr(nlp_ui, "QProcess", _FakeProcess)
    try:
        window.company_combo.setCurrentText("https://www.sikayetvar.com/istikbal")
        window.nlp_process = None
        window.start_nlp_analysis()
        assert isinstance(window.nlp_process, _FakeProcess)
        assert window.nlp_process._state == 1
        assert "mobilitik.nlp_worker" in window.nlp_process.arguments
        assert "istikbal" in window.nlp_process.arguments
        assert str(window.repo.db_path) in window.nlp_process.arguments
        window.stop_nlp_analysis()
        assert window.nlp_process.terminated is True
    finally:
        window.close()
        app.processEvents()


def test_nlp_output_progress_and_install_flow(monkeypatch, tmp_path):
    app, window = _make_window(monkeypatch, tmp_path)
    monkeypatch.setattr(nlp_ui, "QProcess", _FakeProcess)
    try:
        window.nlp_process = _FakeProcess(window)
        window.nlp_process.output = b"NLP_STATUS Model hazirlaniyor\nNLP_PROGRESS 2 5\nNLP_WARNING ornek\n"
        window._read_nlp_output()
        assert window.nlp_progress.maximum() == 5
        assert window.nlp_progress.value() == 2
        assert "ornek" in window.nlp_log.toPlainText()

        window.nlp_process = None
        window.install_nlp_dependencies()
        assert isinstance(window.nlp_install_process, _FakeProcess)
        assert "mobilitik.nlp_installer" in window.nlp_install_process.arguments
        window.nlp_install_process.output = b"NLP_INSTALL_STATUS test\n"
        window._read_nlp_install_output()
        window._nlp_install_finished(0, None)
        assert "başarıyla" in window.nlp_log.toPlainText()
    finally:
        window.close()
        app.processEvents()
