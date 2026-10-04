from __future__ import annotations

import datetime as dt
import sys
from collections import Counter

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.benchmark import compare_companies
from mobilitik.analysis.classifier import classify_record
from mobilitik.analysis.context import analyze_context
from mobilitik.analysis.summary import category_summary
from mobilitik.analysis.verbs import (
    DEFAULT_REGISTERED_ROOTS,
    VerbSentenceMatch,
    find_sentences_with_registered_roots,
    parse_registered_roots,
)
from mobilitik.desktop.advanced_ui import AdvancedMainWindow
from mobilitik.text_quality import analysis_text


MODERN_STYLESHEET = """
QMainWindow, QWidget {
    background: #080d1a;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 9.75pt;
}
QToolTip {
    background: #111c33;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 9pt;
}
QGroupBox {
    background: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #93c5fd;
    font-size: 9.5pt;
    font-weight: 700;
}
QFrame#metricCard, QFrame#dashboardCard {
    background: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 9px;
}
QLabel#metricTitle, QLabel#dashboardTitle {
    color: #94a3b8;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
QLabel#metricValue, QLabel#dashboardValue {
    color: #f8fafc;
    font-size: 17pt;
    font-weight: 800;
}
QLabel#dashboardDetail {
    color: #38bdf8;
    font-size: 8pt;
    font-weight: 500;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 6px;
    padding: 7px 15px;
    font-weight: 600;
}
QPushButton:hover {
    background: #3b82f6;
    border-color: #60a5fa;
}
QPushButton:pressed {
    background: #1d4ed8;
}
QPushButton:disabled {
    background: #1e293b;
    border: 1px solid #334155;
    color: #64748b;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {
    background: #0b1120;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 9px;
    selection-background-color: #0284c7;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #38bdf8;
    background: #0d1527;
}
QComboBox QAbstractItemView {
    background: #0f172a;
    color: #f1f5f9;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    padding: 4px;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    border-radius: 8px;
    top: -1px;
    background: #0b1120;
}
QTabBar::tab {
    background: #0d1527;
    color: #94a3b8;
    border: 1px solid #1e293b;
    border-bottom: none;
    padding: 9px 15px;
    margin-right: 3px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-weight: 600;
}
QTabBar::tab:hover {
    background: #131d31;
    color: #cbd5e1;
}
QTabBar::tab:selected {
    background: #0b1120;
    color: #38bdf8;
    border: 1px solid #1e293b;
    border-bottom: 2px solid #38bdf8;
}
QTableWidget {
    background: #0b1120;
    alternate-background-color: #0f172a;
    color: #e2e8f0;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 7px;
    selection-background-color: #0c4a6e;
    selection-color: #f8fafc;
}
QHeaderView::section {
    background: #131d31;
    color: #94a3b8;
    border: 0;
    border-right: 1px solid #1e293b;
    border-bottom: 1px solid #1e293b;
    padding: 8px 6px;
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 0.3px;
}
QProgressBar {
    background: #0b1120;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #e2e8f0;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 5px;
}
QSplitter::handle:horizontal {
    background: #1e293b;
    width: 5px;
    margin: 4px 0;
    border-radius: 2px;
}
QSplitter::handle:horizontal:hover {
    background: #38bdf8;
}
QSplitter::handle:vertical {
    background: #1e293b;
    height: 5px;
    margin: 0 4px;
    border-radius: 2px;
}
QSplitter::handle:vertical:hover {
    background: #38bdf8;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #334155;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #475569;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
"""


class HorizontalBarChart(QFrame):
    """Small dependency-free horizontal bar chart for dashboard summaries."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.data: list[tuple[str, float]] = []
        self.setMinimumHeight(220)
        self.setObjectName("dashboardCard")

    def set_data(self, rows):
        self.data = [(str(label), float(value)) for label, value in rows if float(value) >= 0][:12]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(16, 14, -16, -14)
        painter.setPen(QColor("#e2e8f0"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize(), 10))
        painter.setFont(font)
        painter.drawText(rect.left(), rect.top() + 16, self.title)

        if not self.data:
            painter.setPen(QColor("#64748b"))
            painter.drawText(rect.adjusted(0, 38, 0, 0), Qt.AlignCenter, "Bu filtre için grafik verisi yok.")
            return

        top = rect.top() + 40
        available = max(rect.height() - 55, 60)
        # Cap row height between 24 and 34 so bars never blow up to 200px in fullscreen!
        row_h = min(34.0, max(24.0, available / max(len(self.data), 1)))
        bar_h = min(16.0, row_h * 0.55)
        label_w = min(280.0, max(140.0, rect.width() * 0.32))
        bar_left = rect.left() + label_w
        bar_w = max(rect.width() - label_w - 55, 40)
        max_value = max(value for _label, value in self.data) or 1.0
        metrics = painter.fontMetrics()

        for index, (label, value) in enumerate(self.data):
            y = top + index * row_h
            if y + row_h > rect.bottom():
                break
            display = metrics.elidedText(label, Qt.ElideRight, int(label_w - 10))
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(QRectF(rect.left(), y, label_w - 8, row_h), Qt.AlignVCenter | Qt.AlignLeft, display)
            width = max(3.0, bar_w * value / max_value) if value > 0 else 0.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0ea5e9"))
            bar_y = y + (row_h - bar_h) / 2
            painter.drawRoundedRect(QRectF(bar_left, bar_y, width, bar_h), 4, 4)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(QRectF(bar_left + bar_w + 6, y, 45, row_h), Qt.AlignVCenter | Qt.AlignRight, f"{value:g}")


class TrendChart(QFrame):
    """Compact line chart used for complaint counts over ordered periods."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.data: list[tuple[str, float]] = []
        self.setMinimumHeight(220)
        self.setObjectName("dashboardCard")

    def set_data(self, rows):
        self.data = [(str(label), float(value)) for label, value in rows]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(18, 14, -18, -18)
        painter.setPen(QColor("#e2e8f0"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize(), 10))
        painter.setFont(font)
        painter.drawText(rect.left(), rect.top() + 16, self.title)
        if not self.data:
            painter.setPen(QColor("#64748b"))
            painter.drawText(rect.adjusted(0, 38, 0, 0), Qt.AlignCenter, "Bu filtre için trend verisi yok.")
            return

        plot = QRectF(rect.left() + 38, rect.top() + 48, max(rect.width() - 48, 60), max(rect.height() - 80, 80))
        max_value = max(value for _label, value in self.data) or 1.0
        painter.setPen(QPen(QColor("#334155"), 1))
        for step in range(5):
            y = plot.top() + plot.height() * step / 4
            painter.drawLine(plot.left(), y, plot.right(), y)
        points = []
        denom = max(len(self.data) - 1, 1)
        for index, (_label, value) in enumerate(self.data):
            x = plot.left() + plot.width() * index / denom
            y = plot.bottom() - plot.height() * value / max_value
            points.append((x, y))
        painter.setPen(QPen(QColor("#38bdf8"), 2.5))
        for first, second in zip(points, points[1:]):
            painter.drawLine(first[0], first[1], second[0], second[1])
        painter.setBrush(QColor("#7dd3fc"))
        painter.setPen(Qt.NoPen)
        for x, y in points:
            painter.drawEllipse(QRectF(x - 3.5, y - 3.5, 7, 7))
        painter.setPen(QColor("#94a3b8"))
        label_indexes = sorted(set([0, len(self.data) // 2, len(self.data) - 1]))
        for index in label_indexes:
            label, _value = self.data[index]
            x, _y = points[index]
            painter.drawText(QRectF(x - 60, plot.bottom() + 7, 120, 22), Qt.AlignHCenter | Qt.AlignTop, label)
        painter.drawText(QRectF(rect.left(), plot.top() - 6, 32, 20), Qt.AlignRight, f"{max_value:g}")
        painter.drawText(QRectF(rect.left(), plot.bottom() - 10, 32, 20), Qt.AlignRight, "0")


class ModernMainWindow(AdvancedMainWindow):
    """Modern, metric-rich Mobilitik workspace with anchored context analysis."""

    def __init__(self):
        self._context_records: dict[str, list[dict]] = {}
        self._registered_roots = list(DEFAULT_REGISTERED_ROOTS)
        self._verb_sentence_matches: list[VerbSentenceMatch] = []
        self._current_sentence_matches: list[VerbSentenceMatch] = []
        super().__init__(defer_initial_refresh=True)
        self._build_dashboard_tab()
        self._build_modern_verb_tab()
        self._build_context_tab()
        self._build_benchmark_tab()
        self._ensure_database_tab_last()
        self.setStyleSheet(MODERN_STYLESHEET)
        self.setWindowTitle("Mobilitik — Tüketici Şikâyeti Araştırma Paneli")
        self.resize(1540, 980)

        # Compact log and window layout margins to prevent vertical squishing
        if hasattr(self, "log"):
            self.log.setMaximumHeight(50)
            self.log.setPlaceholderText("Veri toplama günlüğü burada görüntülenir…")
        central = self.centralWidget()
        if central and central.layout():
            central.layout().setContentsMargins(12, 10, 12, 10)
            central.layout().setSpacing(8)

        self.refresh_analysis()
        self.refresh_nlp_cached_view()

    def start_scraping(self):
        if hasattr(self, "log"):
            self.log.setMaximumHeight(130)
        super().start_scraping()

    def _ensure_database_tab_last(self):
        """Ensure the Database Management tab is positioned at the very end."""
        if hasattr(self, "database_tab") and self.database_tab is not None:
            idx = self.tabs.indexOf(self.database_tab)
            if idx >= 0:
                self.tabs.removeTab(idx)
            self.tabs.addTab(self.database_tab, "Veritabanı Yönetimi")
        if hasattr(self, "dashboard_tab") and self.dashboard_tab is not None:
            self.tabs.setCurrentWidget(self.dashboard_tab)

    def _metric_card(self, title: str, value: str):
        frame = QFrame()
        frame.setObjectName("metricCard")
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        frame.setMinimumHeight(62)
        frame.setMaximumHeight(74)
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 6, 12, 6)
        box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        box.addWidget(title_label)
        box.addWidget(value_label)
        return frame, value_label

    @staticmethod
    def _dashboard_card(title: str):
        frame = QFrame()
        frame.setObjectName("dashboardCard")
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        frame.setMinimumHeight(66)
        frame.setMaximumHeight(80)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("dashboardTitle")
        value_label = QLabel("—")
        value_label.setObjectName("dashboardValue")
        detail_label = QLabel("")
        detail_label.setObjectName("dashboardDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        return frame, value_label, detail_label

    def _build_dashboard_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("dashboardContainer")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(10)

        heading = QLabel("Araştırma Gösterge Paneli")
        heading.setStyleSheet("font-size: 16pt; font-weight: 750; color: #f8fafc;")
        description = QLabel(
            "Seçili firma ve tarih aralığının özet görünümü. Şikâyet sayıları satış hacmine göre normalize edilmemiş platform verileridir."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        outer.addWidget(heading)
        outer.addWidget(description)

        card_box = QVBoxLayout()
        card_box.setSpacing(8)
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        names = [
            "Toplam Şikâyet", "Çözülen", "Çözülmeyen", "Firma Yanıtı",
            "Yanıtsız", "Medyan Yanıt", "Medyan Çözüm", "Sınıflandırılmış",
            "Günlük Ort. Şikâyet",
        ]
        self.dashboard_cards = {name: self._dashboard_card(name) for name in names}
        for name in names[:5]:
            row1.addWidget(self.dashboard_cards[name][0])
        for name in names[5:]:
            row2.addWidget(self.dashboard_cards[name][0])
        card_box.addLayout(row1)
        card_box.addLayout(row2)
        outer.addLayout(card_box)

        chart_split = QSplitter(Qt.Horizontal)
        self.dashboard_category_chart = HorizontalBarChart("En çok görülen şikâyet kategorileri")
        self.dashboard_trend_chart = TrendChart("Şikâyet hacmi eğilimi")
        chart_split.addWidget(self.dashboard_category_chart)
        chart_split.addWidget(self.dashboard_trend_chart)
        chart_split.setSizes([720, 720])
        chart_split.setStretchFactor(0, 1)
        chart_split.setStretchFactor(1, 1)
        outer.addWidget(chart_split)

        category_group = QGroupBox("Kategori oranları")
        category_layout = QVBoxLayout(category_group)
        self.dashboard_category_table = QTableWidget(0, 7)
        self.dashboard_category_table.setMinimumHeight(180)
        self.dashboard_category_table.setHorizontalHeaderLabels(
            ["Kategori", "Şikâyet", "Dönem Payı %", "Çözülen", "Çözülme %", "Yanıt %", "Medyan Yanıt"]
        )
        self.dashboard_category_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dashboard_category_table.setAlternatingRowColors(True)
        self.dashboard_category_table.setSelectionBehavior(QTableWidget.SelectRows)
        dh = self.dashboard_category_table.horizontalHeader()
        dh.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 7):
            dh.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        category_layout.addWidget(self.dashboard_category_table)
        outer.addWidget(category_group)

        scroll.setWidget(container)
        self.dashboard_tab = scroll
        self.tabs.insertTab(0, self.dashboard_tab, "Gösterge Paneli")
        self.tabs.setCurrentWidget(self.dashboard_tab)

    def _build_modern_verb_tab(self):
        """Build the modern verb analysis UI listing sentences ending with registered roots."""
        modern_tab = QWidget()
        outer = QVBoxLayout(modern_tab)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        info = QLabel(
            "<b>Kayıtlı Kök Fiil Analizi:</b> Yaklaşık gövde yaklaşımı bırakılmıştır. "
            "Şikâyet metinleri taranarak sadece kayıtlı doğrulanmış köklerle biten ifadeler tespit edilir ve bu ifadeleri içeren cümleler listelenir."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        outer.addWidget(info)

        controls_group = QGroupBox("Kayıtlı Kök ve Cümle Filtresi")
        controls = QGridLayout(controls_group)
        controls.setContentsMargins(12, 10, 12, 10)
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)

        self.verb_root_filter_combo = QComboBox()
        self.verb_root_filter_combo.addItem("Tümü (Tüm Kayıtlı Kökler)", "Tümü")
        for r in sorted(self._registered_roots):
            self.verb_root_filter_combo.addItem(f"Kök: {r}", r)
        self.verb_root_filter_combo.currentIndexChanged.connect(self._render_modern_verb_sentences)

        self.verb_sentence_search = QLineEdit()
        self.verb_sentence_search.setPlaceholderText("Cümle, ifade veya başlıkta ara…")
        self.verb_sentence_search.setClearButtonEnabled(True)
        self.verb_sentence_search.textChanged.connect(self._render_modern_verb_sentences)

        self.verb_roots_input = QLineEdit()
        self.verb_roots_input.setText("; ".join(self._registered_roots))
        self.verb_roots_input.setPlaceholderText("gel; git; yap; et; çöz; ara; ver; al; kur; ...")
        self.verb_roots_input.setToolTip("Taranacak kayıtlı kökler (noktalı virgülle ayırın).")
        self.verb_roots_input.returnPressed.connect(self.refresh_verb_analysis)

        apply_roots_btn = QPushButton("Kökleri Uygula")
        apply_roots_btn.clicked.connect(self.refresh_verb_analysis)
        reset_roots_btn = QPushButton("Varsayılana Dön")
        reset_roots_btn.clicked.connect(self._reset_verb_roots)

        controls.addWidget(QLabel("Kök Filtresi:"), 0, 0)
        controls.addWidget(self.verb_root_filter_combo, 0, 1)
        controls.addWidget(QLabel("Metin Ara:"), 0, 2)
        controls.addWidget(self.verb_sentence_search, 0, 3)

        controls.addWidget(QLabel("Kayıtlı Kökler:"), 1, 0)
        controls.addWidget(self.verb_roots_input, 1, 1, 1, 3)
        controls.addWidget(apply_roots_btn, 1, 4)
        controls.addWidget(reset_roots_btn, 1, 5)
        outer.addWidget(controls_group)

        # Metric cards
        card_row = QHBoxLayout()
        card_row.setSpacing(10)
        self.verb_cards = {
            "Toplam Cümle": self._dashboard_card("Toplam Cümle"),
            "Eşleşen Kök": self._dashboard_card("Eşleşen Kök"),
            "Farklı İfade": self._dashboard_card("Farklı İfade"),
        }
        for card in self.verb_cards.values():
            card[0].setMaximumHeight(74)
            card_row.addWidget(card[0])
        outer.addLayout(card_row)

        table_group = QGroupBox("Kayıtlı Köklerle Biten İfadeleri İçeren Cümleler — Çift tıklayınca şikâyet açılır")
        table_layout = QVBoxLayout(table_group)
        self.verb_sentence_table = QTableWidget(0, 6)
        self.verb_sentence_table.setMinimumHeight(240)
        self.verb_sentence_table.setHorizontalHeaderLabels([
            "Cümle", "Kayıtlı Kök", "Eşleşen İfade", "Firma", "Tarih", "Şikâyet Başlığı"
        ])
        self.verb_sentence_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verb_sentence_table.setAlternatingRowColors(True)
        self.verb_sentence_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.verb_sentence_table.verticalHeader().setDefaultSectionSize(32)
        vh = self.verb_sentence_table.horizontalHeader()
        vh.setSectionResizeMode(0, QHeaderView.Stretch)
        vh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        vh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        vh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        vh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        vh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.verb_sentence_table.cellDoubleClicked.connect(self._open_verb_sentence_detail)
        table_layout.addWidget(self.verb_sentence_table)
        outer.addWidget(table_group, 1)

        # Compatibility alias
        self.verb_table = self.verb_sentence_table

        # Insert or replace in tabs
        if hasattr(self, "verb_tab") and self.verb_tab in [self.tabs.widget(i) for i in range(self.tabs.count())]:
            idx = self.tabs.indexOf(self.verb_tab)
            self.tabs.removeTab(idx)
            self.verb_tab = modern_tab
            self.tabs.insertTab(idx, self.verb_tab, "Fiil Analizi")
        else:
            self.verb_tab = modern_tab
            self.tabs.addTab(self.verb_tab, "Fiil Analizi")

    def _reset_verb_roots(self):
        self._registered_roots = list(DEFAULT_REGISTERED_ROOTS)
        if hasattr(self, "verb_roots_input"):
            self.verb_roots_input.setText("; ".join(DEFAULT_REGISTERED_ROOTS))
        self.refresh_verb_analysis()

    def _render_modern_verb_sentences(self, *_args):
        if not hasattr(self, "verb_sentence_table"):
            return
        selected_root = self.verb_root_filter_combo.currentData() if hasattr(self, "verb_root_filter_combo") else "Tümü"
        query = self.verb_sentence_search.text().strip().lower() if hasattr(self, "verb_sentence_search") else ""

        filtered: list[VerbSentenceMatch] = []
        unique_roots = set()
        unique_expressions = set()

        for match in self._verb_sentence_matches:
            if selected_root and selected_root != "Tümü" and match.root != selected_root:
                continue
            if query:
                searchable = f"{match.sentence} {match.expression} {match.root} {match.title}".lower()
                if query not in searchable:
                    continue
            filtered.append(match)
            unique_roots.add(match.root)
            unique_expressions.add(match.expression)

        self._current_sentence_matches = filtered
        self.verb_sentence_table.setRowCount(len(filtered))

        for row, match in enumerate(filtered):
            item_sentence = QTableWidgetItem(match.sentence)
            item_sentence.setToolTip(f"Cümle: {match.sentence}\nEşleşen Kök: {match.root}\nİfade: {match.expression}")
            item_root = QTableWidgetItem(match.root)
            item_root.setTextAlignment(Qt.AlignCenter)
            item_expr = QTableWidgetItem(match.expression)
            item_company = QTableWidgetItem(match.company)
            item_company.setTextAlignment(Qt.AlignCenter)
            item_date = QTableWidgetItem(match.date[:10] if match.date else "")
            item_date.setTextAlignment(Qt.AlignCenter)
            item_title = QTableWidgetItem(match.title)
            item_title.setToolTip(match.title)

            self.verb_sentence_table.setItem(row, 0, item_sentence)
            self.verb_sentence_table.setItem(row, 1, item_root)
            self.verb_sentence_table.setItem(row, 2, item_expr)
            self.verb_sentence_table.setItem(row, 3, item_company)
            self.verb_sentence_table.setItem(row, 4, item_date)
            self.verb_sentence_table.setItem(row, 5, item_title)

        if hasattr(self, "verb_cards"):
            self._set_card(self.verb_cards["Toplam Cümle"], str(len(filtered)), f"{len(filtered)} eşleşen cümle")
            self._set_card(self.verb_cards["Eşleşen Kök"], str(len(unique_roots)), f"{len(unique_roots)} farklı kök")
            self._set_card(self.verb_cards["Farklı İfade"], str(len(unique_expressions)), f"{len(unique_expressions)} fiil öbeği")

    def _open_verb_sentence_detail(self, row: int, _col: int = 0):
        if row < 0 or row >= len(self._current_sentence_matches):
            return None
        match = self._current_sentence_matches[row]
        from mobilitik.desktop.drilldown import ComplaintDetailDialog
        dialog = ComplaintDetailDialog(match.record, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        if not hasattr(self, "_open_detail_dialogs"):
            self._open_detail_dialogs = []
        self._open_detail_dialogs.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def refresh_verb_analysis(self, *_args, records=None):
        if records is None:
            records = getattr(self, "_analysis_records", [])
            if not records and hasattr(self, "_filtered_records"):
                records = self._filtered_records()[3]

        roots_text = self.verb_roots_input.text() if hasattr(self, "verb_roots_input") else None
        roots = parse_registered_roots(roots_text) if roots_text else DEFAULT_REGISTERED_ROOTS
        self._registered_roots = list(roots)

        if hasattr(self, "verb_root_filter_combo"):
            current_choice = self.verb_root_filter_combo.currentData() or "Tümü"
            self.verb_root_filter_combo.blockSignals(True)
            self.verb_root_filter_combo.clear()
            self.verb_root_filter_combo.addItem("Tümü (Tüm Kayıtlı Kökler)", "Tümü")
            for r in sorted(roots):
                self.verb_root_filter_combo.addItem(f"Kök: {r}", r)
            idx = 0
            for i in range(self.verb_root_filter_combo.count()):
                if self.verb_root_filter_combo.itemData(i) == current_choice:
                    idx = i
                    break
            self.verb_root_filter_combo.setCurrentIndex(idx)
            self.verb_root_filter_combo.blockSignals(False)

        self._verb_sentence_matches = find_sentences_with_registered_roots(records, roots=roots)
        self._render_modern_verb_sentences()

    def _build_context_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("contextContainer")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(10)

        info = QLabel(
            "<b>Bağlam Analizi:</b> Bir çapa kelime veya ifadenin hemen öncesindeki veya sonrasındaki sözcükleri analiz eder. "
            "Örn. ‘koltuk takımı’ + Sol + 1 kelime → model adları; ‘bayi*’ + Sol + 2 kelime → bayi / şehir isimleri."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        outer.addWidget(info)

        controls_group = QGroupBox("Bağlam Sorgu Parametreleri")
        controls = QGridLayout(controls_group)
        controls.setContentsMargins(12, 10, 12, 10)
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)

        self.context_anchor = QComboBox()
        self.context_anchor.setEditable(True)
        self.context_anchor.addItems(["koltuk takımı", "bayi*", "mağaza*", "servis", "teslimat", "kumaş"])

        self.context_direction = QComboBox()
        self.context_direction.addItem("Sol — önceki kelimeler", "left")
        self.context_direction.addItem("Sağ — sonraki kelimeler", "right")
        self.context_direction.addItem("İki yön", "both")

        self.context_window = QSpinBox()
        self.context_window.setRange(1, 5)
        self.context_window.setValue(1)
        self.context_window.setSuffix(" kelime")

        self.context_min_count = QSpinBox()
        self.context_min_count.setRange(1, 9999)
        self.context_min_count.setValue(1)

        self.context_top_k = QSpinBox()
        self.context_top_k.setRange(10, 200)
        self.context_top_k.setValue(50)

        self.context_run_button = QPushButton("🔍 Bağlamı Analiz Et")
        self.context_run_button.setMinimumWidth(180)
        self.context_run_button.clicked.connect(self.refresh_context_analysis)

        controls.addWidget(QLabel("Çapa İfade:"), 0, 0)
        controls.addWidget(self.context_anchor, 0, 1)
        controls.addWidget(QLabel("Yön:"), 0, 2)
        controls.addWidget(self.context_direction, 0, 3)
        controls.addWidget(QLabel("Bağlam Uzunluğu:"), 0, 4)
        controls.addWidget(self.context_window, 0, 5)

        controls.addWidget(QLabel("Min. Tekrar:"), 1, 0)
        controls.addWidget(self.context_min_count, 1, 1)
        controls.addWidget(QLabel("Maks. Sonuç:"), 1, 2)
        controls.addWidget(self.context_top_k, 1, 3)
        controls.addWidget(self.context_run_button, 1, 4, 1, 2)
        outer.addWidget(controls_group)

        # 4 Cards with constrained height so they don't blow up vertically in fullscreen
        card_row = QHBoxLayout()
        card_row.setSpacing(10)
        self.context_cards = {
            "Dönem Şikâyeti": self._dashboard_card("Dönem Şikâyeti"),
            "Çapayı İçeren": self._dashboard_card("Çapayı İçeren"),
            "Çapa Geçişi": self._dashboard_card("Çapa Geçişi"),
            "Benzersiz Bağlam": self._dashboard_card("Benzersiz Bağlam"),
        }
        for card in self.context_cards.values():
            card_row.addWidget(card[0])
        outer.addLayout(card_row)

        splitter = QSplitter(Qt.Horizontal)
        table_group = QGroupBox("Bağlam Sonuçları — Çift tıklayınca ilişkili şikâyetler açılır")
        table_layout = QVBoxLayout(table_group)
        self.context_table = QTableWidget(0, 5)
        self.context_table.setMinimumHeight(220)
        self.context_table.setHorizontalHeaderLabels(
            ["Bağlam", "Geçiş", "Şikâyet", "Çapa İçinde %", "Dönem İçinde %"]
        )
        self.context_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.context_table.setAlternatingRowColors(True)
        self.context_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.context_table.verticalHeader().setDefaultSectionSize(28)
        self.context_table.cellDoubleClicked.connect(self._open_context_matches)
        ch = self.context_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            ch.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.context_table)
        splitter.addWidget(table_group)

        chart_group = QGroupBox("Bağlam Grafiği — En Sık Geçişler")
        chart_layout = QVBoxLayout(chart_group)
        self.context_chart = HorizontalBarChart("En sık bağlamlar — farklı şikâyet sayısı")
        self.context_chart.setMinimumHeight(220)
        chart_layout.addWidget(self.context_chart)
        splitter.addWidget(chart_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([850, 550])
        outer.addWidget(splitter, 1)

        scroll.setWidget(container)
        self.context_tab = scroll
        self.tabs.addTab(self.context_tab, "Bağlam Analizi")

    def refresh_analysis(self):
        super().refresh_analysis()
        if hasattr(self, "dashboard_cards"):
            self._refresh_dashboard()
        if hasattr(self, "context_table") and self.context_anchor.currentText().strip():
            self.refresh_context_analysis()

    @staticmethod
    def _set_card(card, value: str, detail: str = ""):
        card[1].setText(value)
        card[2].setText(detail)

    def _refresh_dashboard(self):
        records = list(getattr(self, "_analysis_records", []))
        total = len(records)
        resolved = sum(bool(record.get("resolved")) for record in records)
        responded = sum(bool(record.get("company_responded")) for record in records)
        unresolved = total - resolved
        unanswered = total - responded
        response_hours = sorted(float(record["response_hours"]) for record in records if record.get("response_hours") is not None)
        resolution_hours = sorted(float(record["resolution_hours"]) for record in records if record.get("resolution_hours") is not None)

        def median(values):
            if not values:
                return None
            middle = len(values) // 2
            if len(values) % 2:
                return values[middle]
            return (values[middle - 1] + values[middle]) / 2

        classified = 0
        for record in records:
            result = classify_record(record.get("title"), record.get("complaint_text"))
            if result.categories:
                classified += 1
        dates = [str(record.get("complaint_date") or "")[:10] for record in records if record.get("complaint_date")]
        active_days = len(set(date for date in dates if date))
        per_day = (total / active_days) if active_days else 0.0

        self._set_card(self.dashboard_cards["Toplam Şikâyet"], str(total), f"{active_days} aktif gün")
        self._set_card(self.dashboard_cards["Çözülen"], str(resolved), self._pct(resolved, total))
        self._set_card(self.dashboard_cards["Çözülmeyen"], str(unresolved), self._pct(unresolved, total))
        self._set_card(self.dashboard_cards["Firma Yanıtı"], str(responded), self._pct(responded, total))
        self._set_card(self.dashboard_cards["Yanıtsız"], str(unanswered), self._pct(unanswered, total))
        self._set_card(self.dashboard_cards["Medyan Yanıt"], self._duration(median(response_hours)), f"{len(response_hours)} zamanlı kayıt")
        self._set_card(self.dashboard_cards["Medyan Çözüm"], self._duration(median(resolution_hours)), f"{len(resolution_hours)} zamanlı kayıt")
        self._set_card(self.dashboard_cards["Sınıflandırılmış"], str(classified), self._pct(classified, total))
        self._set_card(self.dashboard_cards["Günlük Ort. Şikâyet"], f"{per_day:.1f}", "şikâyet / aktif gün" if active_days else "—")

        summary = category_summary(records)
        category_rows = [row for row in summary if row["category"] != "Tümü"]
        self.dashboard_category_chart.set_data(
            [(row["category"], row["complaints"]) for row in sorted(category_rows, key=lambda row: row["complaints"], reverse=True)]
        )
        self.dashboard_category_table.setRowCount(len(category_rows))
        for r, row in enumerate(category_rows):
            period_share = (row["complaints"] / total * 100.0) if total else 0.0
            values = [
                row["category"], row["complaints"], f"%{period_share:.1f}", row["resolved"],
                f"%{row['resolved_rate']:.1f}", f"%{row['response_rate']:.1f}", self._duration(row["median_response_hours"]),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.dashboard_category_table.setItem(r, c, item)

        parsed_dates = []
        for date_text in dates:
            try:
                parsed_dates.append(dt.date.fromisoformat(date_text))
            except ValueError:
                pass
        daily_mode = bool(parsed_dates) and (max(parsed_dates) - min(parsed_dates)).days <= 45
        trend_counts: Counter[str] = Counter()
        for date_value in parsed_dates:
            key = date_value.strftime("%d.%m") if daily_mode else date_value.strftime("%Y-%m")
            trend_counts[key] += 1
        self.dashboard_trend_chart.title = "Günlük şikâyet eğilimi" if daily_mode else "Aylık şikâyet eğilimi"
        self.dashboard_trend_chart.set_data(sorted(trend_counts.items()))

    def refresh_context_analysis(self, *_args):
        if not hasattr(self, "context_table"):
            return
        anchor = self.context_anchor.currentText().strip()
        direction = self.context_direction.currentData() or "left"
        records = list(getattr(self, "_analysis_records", []))
        hits, mapping, meta = analyze_context(
            records,
            anchor,
            direction=direction,
            window=self.context_window.value(),
            min_count=self.context_min_count.value(),
            top_k=self.context_top_k.value(),
        )
        self._context_records = mapping
        self.context_table.setRowCount(len(hits))
        for r, hit in enumerate(hits):
            values = [
                hit.context,
                hit.count,
                hit.document_count,
                f"%{hit.anchor_share * 100:.1f}",
                f"%{hit.period_share * 100:.1f}",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.context_table.setItem(r, c, item)
        self.context_chart.set_data([(hit.context, hit.document_count) for hit in hits[:12]])

        anchor_docs = meta["anchor_documents"]
        self._set_card(self.context_cards["Dönem Şikâyeti"], str(meta["records"]), "seçili filtre")
        self._set_card(
            self.context_cards["Çapayı İçeren"],
            str(anchor_docs),
            self._pct(anchor_docs, meta["records"]),
        )
        self._set_card(self.context_cards["Çapa Geçişi"], str(meta["anchor_mentions"]), "toplam kullanım")
        self._set_card(self.context_cards["Benzersiz Bağlam"], str(meta["unique_contexts"]), f"min. tekrar ≥ {self.context_min_count.value()}")

    def _open_context_matches(self, row: int, _column: int = 0):
        item = self.context_table.item(row, 0)
        if item is None:
            return
        context = item.text()
        records = self._context_records.get(context, [])
        anchor = self.context_anchor.currentText().strip()
        self._open_records_dialog(f"Bağlam: {context} — Çapa: {anchor}", records)

    def _build_benchmark_tab(self):
        self.benchmark_tab = QWidget()
        outer = QVBoxLayout(self.benchmark_tab)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        info = QLabel(
            "İki firmanın seçilen dönemdeki şikâyet hacmi, çözülme ve yanıt oranları ile "
            "medyan sürelerini doğrudan yan yana kıyaslayın."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8;")
        outer.addWidget(info)

        controls_group = QGroupBox("Karşılaştırma Seçenekleri")
        controls = QHBoxLayout(controls_group)
        controls.addWidget(QLabel("Firma 1:"))
        self.benchmark_c1 = QComboBox()
        self.benchmark_c1.setEditable(True)
        self.benchmark_c1.addItems(["istikbal", "bellona", "kelebek-mobilya"])
        controls.addWidget(self.benchmark_c1)

        controls.addWidget(QLabel("Firma 2:"))
        self.benchmark_c2 = QComboBox()
        self.benchmark_c2.setEditable(True)
        self.benchmark_c2.addItems(["bellona", "istikbal", "kelebek-mobilya"])
        controls.addWidget(self.benchmark_c2)

        self.benchmark_run_button = QPushButton("Firmaları Karşılaştır")
        self.benchmark_run_button.clicked.connect(self._run_benchmark)
        controls.addWidget(self.benchmark_run_button)
        controls.addStretch()
        outer.addWidget(controls_group)

        self.benchmark_table = QTableWidget(0, 3)
        self.benchmark_table.setMinimumHeight(220)
        self.benchmark_table.setHorizontalHeaderLabels(["Performans Metriği", "Firma 1", "Firma 2"])
        self.benchmark_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.benchmark_table.setAlternatingRowColors(True)
        bh = self.benchmark_table.horizontalHeader()
        bh.setSectionResizeMode(0, QHeaderView.Stretch)
        bh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        bh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        outer.addWidget(self.benchmark_table, 1)

        self.tabs.addTab(self.benchmark_tab, "Firma Karşılaştırma")

    def _run_benchmark(self):
        c1 = self.benchmark_c1.currentText().strip()
        c2 = self.benchmark_c2.currentText().strip()
        if not c1 or not c2:
            return
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        data = compare_companies(self.repo, c1, c2, start_date=start, end_date=end)

        self.benchmark_table.setHorizontalHeaderLabels(
            ["Performans Metriği", data["company1"]["name"].upper(), data["company2"]["name"].upper()]
        )
        rows = data["rows"]
        self.benchmark_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            item_metric = QTableWidgetItem(row["metric"])
            item_c1 = QTableWidgetItem(row["c1_val"])
            item_c2 = QTableWidgetItem(row["c2_val"])
            item_c1.setTextAlignment(Qt.AlignCenter)
            item_c2.setTextAlignment(Qt.AlignCenter)
            self.benchmark_table.setItem(r, 0, item_metric)
            self.benchmark_table.setItem(r, 1, item_c1)
            self.benchmark_table.setItem(r, 2, item_c2)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mobilitik")
    window = ModernMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
