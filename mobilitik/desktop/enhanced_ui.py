from __future__ import annotations

import html
import sys

from PySide6.QtCore import QEvent, QProcess, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.classifier import classify_record
from mobilitik.analysis.sentiment import ANALYZER_VERSION, DEFAULT_MODEL_ID
from mobilitik.analysis.textstats import normalize_text
from mobilitik.desktop.app import APP_TITLE
from mobilitik.desktop.nlp_ui import NlpMainWindow


class EnhancedMainWindow(NlpMainWindow):
    """User-facing Mobilitik window with drill-down and responsive NLP UI."""

    def __init__(self):
        self._hover_records: list[dict] = []
        self._distinctive_match_records: list[dict] = []
        super().__init__()
        self._setup_complaint_hover()
        self._setup_distinctive_drilldown()
        self.refresh_analysis()
        self.refresh_nlp_cached_view()

    # ------------------------------------------------------------------
    # Complaint hover preview
    # ------------------------------------------------------------------
    def _render_complaints(self, records: list[dict] | None = None):
        records = records if records is not None else getattr(self, "_analysis_records", [])
        try:
            self._hover_records = list(self._records_for_selected_category(records))
        except (AttributeError, RuntimeError):
            self._hover_records = list(records or [])

        super()._render_complaints(records)
        if not hasattr(self, "table"):
            return

        self.table.setMouseTracking(True)
        for row in range(self.table.rowCount()):
            preview = self._tooltip_text(self._hover_records[row]) if row < len(self._hover_records) else ""
            for col in range(self.table.columnCount() - 1):
                item = self.table.item(row, col)
                if item is not None:
                    item.setToolTip(preview)
            link = self.table.cellWidget(row, 7)
            if link is not None:
                link.setToolTip(preview)
                link.setProperty("complaintPreview", preview)
                link.installEventFilter(self)

    def _setup_complaint_hover(self):
        self.table.setMouseTracking(True)
        self.table.itemEntered.connect(self._show_complaint_hover)

    def _show_complaint_hover(self, item: QTableWidgetItem):
        row = item.row()
        if row < 0 or row >= len(self._hover_records):
            return
        preview = self._tooltip_text(self._hover_records[row])
        QToolTip.showText(QCursor.pos(), preview, self.table, self.table.rect(), 12000)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Enter:
            preview = watched.property("complaintPreview") if hasattr(watched, "property") else None
            if preview:
                QToolTip.showText(QCursor.pos(), str(preview), watched, watched.rect(), 12000)
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Distinctive-term -> complaint drill-down
    # ------------------------------------------------------------------
    def _setup_distinctive_drilldown(self):
        layout = self.distinctive_tab.layout()
        if layout is None:
            return

        layout.removeWidget(self.distinctive_table)
        splitter = QSplitter(Qt.Vertical, self.distinctive_tab)
        splitter.addWidget(self.distinctive_table)

        result_group = QGroupBox("Seçilen ifadeyi içeren şikâyetler")
        result_layout = QVBoxLayout(result_group)
        self.distinctive_match_label = QLabel(
            "Yukarıdaki bir kelime/ifadeye tıklayın; seçili kategori ve dönem içinde o ifadeyi içeren şikâyetler burada gösterilir."
        )
        self.distinctive_match_label.setWordWrap(True)
        self.distinctive_match_label.setStyleSheet("color: #666;")
        result_layout.addWidget(self.distinctive_match_label)

        self.distinctive_match_table = QTableWidget(0, 4)
        self.distinctive_match_table.setHorizontalHeaderLabels(
            ["Tarih", "Başlık", "Şikâyet Metni", "Kaynak"]
        )
        self.distinctive_match_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.distinctive_match_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.distinctive_match_table.setAlternatingRowColors(True)
        self.distinctive_match_table.setWordWrap(True)
        self.distinctive_match_table.verticalHeader().setDefaultSectionSize(82)
        match_header = self.distinctive_match_table.horizontalHeader()
        match_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        match_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        match_header.setSectionResizeMode(2, QHeaderView.Stretch)
        match_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.distinctive_match_table.cellClicked.connect(self._show_distinctive_match_preview)
        result_layout.addWidget(self.distinctive_match_table, 1)

        self.distinctive_preview = QTextEdit()
        self.distinctive_preview.setReadOnly(True)
        self.distinctive_preview.setPlaceholderText("Bir eşleşen şikâyeti seçtiğinizde tam metin burada görünür.")
        self.distinctive_preview.setMaximumHeight(150)
        result_layout.addWidget(self.distinctive_preview)

        splitter.addWidget(result_group)
        splitter.setSizes([330, 420])
        layout.addWidget(splitter, 1)

        self.distinctive_table.cellClicked.connect(self._show_distinctive_matches)

    @staticmethod
    def _record_contains_term(record: dict, term: str) -> bool:
        phrase = normalize_text(term).strip()
        if not phrase:
            return False
        text = normalize_text(
            f"{record.get('title') or ''} {record.get('complaint_text') or ''}"
        ).strip()
        return f" {phrase} " in f" {text} "

    def _records_for_distinctive_category(self) -> list[dict]:
        category = self.distinctive_category_combo.currentText() or "Tümü"
        records = list(getattr(self, "_analysis_records", []))
        if category == "Tümü":
            return records
        selected = []
        for record in records:
            result = classify_record(record.get("title"), record.get("complaint_text"))
            categories = result.categories or ["Diğer"]
            if category in categories:
                selected.append(record)
        return selected

    def _show_distinctive_matches(self, row: int, _column: int = 0):
        term_item = self.distinctive_table.item(row, 0)
        if term_item is None:
            return
        self._show_distinctive_matches_for_term(term_item.text())

    def _show_distinctive_matches_for_term(self, term: str):
        if not hasattr(self, "distinctive_match_table"):
            return
        matches = [
            record
            for record in self._records_for_distinctive_category()
            if self._record_contains_term(record, term)
        ]
        self._distinctive_match_records = matches
        self.distinctive_match_label.setText(
            f"“{term}” ifadesini içeren {len(matches)} şikâyet gösteriliyor. Satıra tıklayınca tam metin altta açılır."
        )
        self.distinctive_match_table.setRowCount(len(matches))
        self.distinctive_preview.clear()

        for r, record in enumerate(matches):
            complaint_text = (record.get("complaint_text") or "").strip()
            values = [
                record.get("complaint_date") or "",
                record.get("title") or "",
                complaint_text,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(complaint_text or "Şikâyet metni bulunamadı.")
                self.distinctive_match_table.setItem(r, c, item)

            url = record.get("complaint_url") or ""
            link = QLabel()
            if url:
                safe_url = html.escape(url, quote=True)
                link.setText(f'<a href="{safe_url}">Aç ↗</a>')
                link.setOpenExternalLinks(True)
                link.setTextInteractionFlags(Qt.TextBrowserInteraction)
            else:
                link.setText("—")
            self.distinctive_match_table.setCellWidget(r, 3, link)

    def _show_distinctive_match_preview(self, row: int, _column: int = 0):
        if row < 0 or row >= len(self._distinctive_match_records):
            return
        record = self._distinctive_match_records[row]
        title = record.get("title") or "Başlıksız şikâyet"
        text = record.get("complaint_text") or "Şikâyet metni bulunamadı."
        self.distinctive_preview.setPlainText(f"{title}\n\n{text}")

    def _render_distinctive_category(self, *_args):
        super()._render_distinctive_category(*_args)
        if hasattr(self, "distinctive_match_table"):
            self._distinctive_match_records = []
            self.distinctive_match_table.setRowCount(0)
            self.distinctive_preview.clear()
            self.distinctive_match_label.setText(
                "Bir kelime/ifadeye tıklayın; eşleşen şikâyetler burada gösterilir."
            )

    # ------------------------------------------------------------------
    # Responsive NLP workspace
    # ------------------------------------------------------------------
    def _build_nlp_tab(self):
        self.nlp_tab = QWidget()
        outer = QVBoxLayout(self.nlp_tab)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        info = QLabel(
            "BERTurk analizi isteğe bağlıdır; uygulama açılırken model yüklenmez. "
            "İlk analizde model indirilir, sonuçlar SQLite'ta önbelleğe alınır ve değişmeyen kayıtlar yeniden hesaplanmaz."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555;")
        outer.addWidget(info)

        self.nlp_inner_tabs = QTabWidget()
        outer.addWidget(self.nlp_inner_tabs, 1)

        # 1) Run / status ------------------------------------------------
        run_scroll = QScrollArea()
        run_scroll.setWidgetResizable(True)
        run_page = QWidget()
        run_layout = QVBoxLayout(run_page)
        run_layout.setContentsMargins(12, 12, 12, 12)
        run_layout.setSpacing(12)

        model_group = QGroupBox("Model ve Çalıştırma")
        model_layout = QGridLayout(model_group)
        model_layout.setColumnStretch(1, 1)
        model_value = QLabel(DEFAULT_MODEL_ID)
        model_value.setWordWrap(True)
        model_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        model_value.setToolTip("3 sınıflı Türkçe BERTurk modeli: Negatif / Nötr / Pozitif")
        model_layout.addWidget(QLabel("Model"), 0, 0, Qt.AlignTop)
        model_layout.addWidget(model_value, 0, 1, 1, 2)
        model_layout.addWidget(QLabel("Analiz sürümü"), 1, 0)
        model_layout.addWidget(QLabel(ANALYZER_VERSION), 1, 1, 1, 2)

        self.nlp_install_button = QPushButton("NLP Bileşenlerini Kur / Güncelle")
        self.nlp_install_button.clicked.connect(self.install_nlp_dependencies)
        self.nlp_start_button = QPushButton("Duygu Analizini Başlat")
        self.nlp_start_button.clicked.connect(self.start_nlp_analysis)
        self.nlp_stop_button = QPushButton("Durdur")
        self.nlp_stop_button.setEnabled(False)
        self.nlp_stop_button.clicked.connect(self.stop_nlp_analysis)
        self.nlp_refresh_button = QPushButton("Önbellekteki Sonuçları Yenile")
        self.nlp_refresh_button.clicked.connect(self.refresh_nlp_cached_view)
        model_layout.addWidget(self.nlp_install_button, 2, 0, 1, 2)
        model_layout.addWidget(self.nlp_start_button, 2, 2)
        model_layout.addWidget(self.nlp_stop_button, 3, 0)
        model_layout.addWidget(self.nlp_refresh_button, 3, 1, 1, 2)
        run_layout.addWidget(model_group)

        status_group = QGroupBox("Durum")
        status_layout = QVBoxLayout(status_group)
        self.nlp_progress = QProgressBar()
        self.nlp_progress.setRange(0, 1)
        self.nlp_progress.setValue(0)
        self.nlp_status = QLabel("Hazır — model çalışmıyor.")
        self.nlp_status.setWordWrap(True)
        self.nlp_status.setStyleSheet("color: #666;")
        status_layout.addWidget(self.nlp_progress)
        status_layout.addWidget(self.nlp_status)
        run_layout.addWidget(status_group)

        metrics_group = QGroupBox("Seçili Firma / Dönem Özeti")
        metrics = QGridLayout(metrics_group)
        self.nlp_total_card = self._metric_card("Analiz Edilen", "0")
        self.nlp_negative_card = self._metric_card("Negatif", "—")
        self.nlp_neutral_card = self._metric_card("Nötr", "—")
        self.nlp_positive_card = self._metric_card("Pozitif", "—")
        self.nlp_intensity_card = self._metric_card("Ort. Negatiflik", "—")
        cards = [
            self.nlp_total_card,
            self.nlp_negative_card,
            self.nlp_neutral_card,
            self.nlp_positive_card,
            self.nlp_intensity_card,
        ]
        for index, card in enumerate(cards):
            row, col = divmod(index, 3)
            metrics.addWidget(card[0], row, col)
        run_layout.addWidget(metrics_group)
        run_layout.addStretch()
        run_scroll.setWidget(run_page)
        self.nlp_inner_tabs.addTab(run_scroll, "Çalıştırma")

        # 2) Individual complaint sentiment -----------------------------
        sentiment_page = QWidget()
        sentiment_layout = QVBoxLayout(sentiment_page)
        sentiment_info = QLabel(
            "Her şikâyetin BERTurk Negatif / Nötr / Pozitif dağılımı. Başlık üzerine gelerek metni görebilirsiniz."
        )
        sentiment_info.setWordWrap(True)
        sentiment_info.setStyleSheet("color: #666;")
        sentiment_layout.addWidget(sentiment_info)
        self.nlp_table = QTableWidget(0, 7)
        self.nlp_table.setHorizontalHeaderLabels(
            ["Tarih", "Başlık", "Duygu", "Güven", "Negatif %", "Nötr %", "Pozitif %"]
        )
        self.nlp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nlp_table.setAlternatingRowColors(True)
        sentiment_header = self.nlp_table.horizontalHeader()
        sentiment_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        sentiment_header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 7):
            sentiment_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        sentiment_layout.addWidget(self.nlp_table, 1)
        self.nlp_inner_tabs.addTab(sentiment_page, "Şikâyet Duyguları")

        # 3) Aspect / development priorities ----------------------------
        priority_page = QWidget()
        priority_layout = QVBoxLayout(priority_page)
        explanation = QLabel(
            "Şikâyet cümleleri manuel Mobilitik kategorileriyle eşleştirilir. Öncelik göstergesi; sıklık, negatiflik ve çözülmeme ağırlıklarının şeffaf birleşimidir. Ağırlıkları siz değiştirebilirsiniz."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666;")
        priority_layout.addWidget(explanation)

        weight_group = QGroupBox("Gelişim Önceliği Ağırlıkları")
        weight_layout = QGridLayout(weight_group)
        self.frequency_weight = self._weight_spin(40)
        self.negativity_weight = self._weight_spin(35)
        self.unresolved_weight = self._weight_spin(25)
        weight_layout.addWidget(QLabel("Sıklık"), 0, 0)
        weight_layout.addWidget(self.frequency_weight, 0, 1)
        weight_layout.addWidget(QLabel("Negatiflik"), 0, 2)
        weight_layout.addWidget(self.negativity_weight, 0, 3)
        weight_layout.addWidget(QLabel("Çözülmeme"), 1, 0)
        weight_layout.addWidget(self.unresolved_weight, 1, 1)
        recalc = QPushButton("Öncelikleri Yeniden Hesapla")
        recalc.clicked.connect(self.refresh_nlp_cached_view)
        weight_layout.addWidget(recalc, 1, 2, 1, 2)
        priority_layout.addWidget(weight_group)

        self.priority_table = QTableWidget(0, 8)
        self.priority_table.setHorizontalHeaderLabels(
            [
                "Kategori",
                "Şikâyet",
                "Pay %",
                "Ort. Negatiflik %",
                "Yüksek Negatif %",
                "Çözülmeme %",
                "Ort. Yanıt Süresi",
                "Öncelik",
            ]
        )
        self.priority_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.priority_table.setAlternatingRowColors(True)
        pheader = self.priority_table.horizontalHeader()
        pheader.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 8):
            pheader.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        priority_layout.addWidget(self.priority_table, 1)
        self.nlp_inner_tabs.addTab(priority_page, "Gelişim Öncelikleri")

        # 4) Log ---------------------------------------------------------
        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        log_help = QLabel("Model kurulumu, indirme ve analiz ilerlemesi burada gösterilir.")
        log_help.setStyleSheet("color: #666;")
        log_layout.addWidget(log_help)
        self.nlp_log = QTextEdit()
        self.nlp_log.setReadOnly(True)
        log_layout.addWidget(self.nlp_log, 1)
        self.nlp_inner_tabs.addTab(log_page, "NLP Günlüğü")

        self.tabs.addTab(self.nlp_tab, "NLP / Duygu Analizi")

    @staticmethod
    def _weight_spin(value: int):
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix(" %")
        spin.setMinimumWidth(90)
        return spin


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = EnhancedMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
