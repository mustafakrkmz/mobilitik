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
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.classifier import classify_record
from mobilitik.analysis.context import analyze_context
from mobilitik.analysis.summary import category_summary
from mobilitik.desktop.advanced_ui import AdvancedMainWindow
from mobilitik.text_quality import analysis_text


MODERN_STYLESHEET = """
QMainWindow, QWidget {
    background: #0b1220;
    color: #e5e7eb;
    font-size: 10pt;
}
QToolTip {
    background: #172033;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 7px;
}
QGroupBox {
    background: #111827;
    border: 1px solid #243247;
    border-radius: 10px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #cbd5e1;
}
QFrame#metricCard, QFrame#dashboardCard {
    background: #111827;
    border: 1px solid #243247;
    border-radius: 12px;
}
QLabel#metricTitle, QLabel#dashboardTitle {
    color: #94a3b8;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#metricValue, QLabel#dashboardValue {
    color: #f8fafc;
    font-size: 21pt;
    font-weight: 750;
}
QLabel#dashboardDetail {
    color: #7dd3fc;
    font-size: 9pt;
}
QPushButton {
    background: #1d4ed8;
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #2563eb; }
QPushButton:disabled { background: #263246; color: #64748b; }
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {
    background: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 6px;
    selection-background-color: #0369a1;
}
QComboBox QAbstractItemView {
    background: #111827;
    color: #e5e7eb;
    selection-background-color: #1d4ed8;
}
QTabWidget::pane {
    border: 1px solid #243247;
    border-radius: 9px;
    top: -1px;
    background: #0f172a;
}
QTabBar::tab {
    background: #111827;
    color: #94a3b8;
    border: 1px solid #243247;
    padding: 9px 13px;
    margin-right: 2px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}
QTabBar::tab:selected {
    background: #172033;
    color: #f8fafc;
    border-bottom: 2px solid #38bdf8;
}
QTableWidget {
    background: #0f172a;
    alternate-background-color: #111827;
    color: #e5e7eb;
    gridline-color: #243247;
    border: 1px solid #243247;
    border-radius: 7px;
    selection-background-color: #075985;
}
QHeaderView::section {
    background: #172033;
    color: #cbd5e1;
    border: 0;
    border-right: 1px solid #243247;
    padding: 7px;
    font-weight: 650;
}
QProgressBar {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #e5e7eb;
}
QProgressBar::chunk { background: #0ea5e9; border-radius: 5px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #0f172a; border: none; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #334155; border-radius: 5px; min-height: 24px; min-width: 24px; }
"""


class HorizontalBarChart(QFrame):
    """Small dependency-free horizontal bar chart for dashboard summaries."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.data: list[tuple[str, float]] = []
        self.setMinimumHeight(280)
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

        top = rect.top() + 38
        available = max(rect.height() - 50, 80)
        row_h = max(18.0, available / max(len(self.data), 1))
        label_w = min(190.0, rect.width() * 0.38)
        bar_left = rect.left() + label_w
        bar_w = max(rect.width() - label_w - 44, 50)
        max_value = max(value for _label, value in self.data) or 1.0
        metrics = painter.fontMetrics()

        for index, (label, value) in enumerate(self.data):
            y = top + index * row_h
            display = metrics.elidedText(label, Qt.ElideRight, int(label_w - 10))
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(QRectF(rect.left(), y, label_w - 8, row_h), Qt.AlignVCenter | Qt.AlignLeft, display)
            width = max(2.0, bar_w * value / max_value) if value > 0 else 0.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0ea5e9"))
            painter.drawRoundedRect(QRectF(bar_left, y + row_h * 0.22, width, row_h * 0.56), 4, 4)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(QRectF(bar_left + bar_w + 6, y, 38, row_h), Qt.AlignVCenter | Qt.AlignRight, f"{value:g}")


class TrendChart(QFrame):
    """Compact line chart used for complaint counts over ordered periods."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.data: list[tuple[str, float]] = []
        self.setMinimumHeight(280)
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
        super().__init__()
        self._build_dashboard_tab()
        self._build_context_tab()
        self.setStyleSheet(MODERN_STYLESHEET)
        self.setWindowTitle("Mobilitik — Tüketici Şikâyeti Araştırma Paneli")
        self.resize(1540, 980)
        self.refresh_analysis()

    def _metric_card(self, title: str, value: str):
        frame = QFrame()
        frame.setObjectName("metricCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 11, 14, 11)
        box.setSpacing(4)
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
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)
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
        self.dashboard_tab = QWidget()
        outer = QVBoxLayout(self.dashboard_tab)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        heading = QLabel("Araştırma Gösterge Paneli")
        heading.setStyleSheet("font-size: 18pt; font-weight: 750; color: #f8fafc;")
        description = QLabel(
            "Seçili firma ve tarih aralığının özet görünümü. Şikâyet sayıları satış hacmine göre normalize edilmemiş platform verileridir."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #94a3b8;")
        outer.addWidget(heading)
        outer.addWidget(description)

        card_grid = QGridLayout()
        card_grid.setHorizontalSpacing(10)
        card_grid.setVerticalSpacing(10)
        names = [
            "Toplam Şikâyet", "Çözülen", "Çözülmeyen", "Firma Yanıtı",
            "Yanıtsız", "Medyan Yanıt", "Medyan Çözüm", "Sınıflandırılmış",
            "Günlük Ort. Şikâyet",
        ]
        self.dashboard_cards = {name: self._dashboard_card(name) for name in names}
        for index, name in enumerate(names):
            row, col = divmod(index, 3)
            card_grid.addWidget(self.dashboard_cards[name][0], row, col)
        outer.addLayout(card_grid)

        chart_split = QSplitter(Qt.Horizontal)
        self.dashboard_category_chart = HorizontalBarChart("En çok görülen şikâyet kategorileri")
        self.dashboard_trend_chart = TrendChart("Şikâyet hacmi eğilimi")
        chart_split.addWidget(self.dashboard_category_chart)
        chart_split.addWidget(self.dashboard_trend_chart)
        chart_split.setSizes([720, 720])
        outer.addWidget(chart_split)

        category_group = QGroupBox("Kategori oranları")
        category_layout = QVBoxLayout(category_group)
        self.dashboard_category_table = QTableWidget(0, 7)
        self.dashboard_category_table.setHorizontalHeaderLabels(
            ["Kategori", "Şikâyet", "Dönem Payı %", "Çözülen", "Çözülme %", "Yanıt %", "Medyan Yanıt"]
        )
        self.dashboard_category_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dashboard_category_table.setAlternatingRowColors(True)
        dh = self.dashboard_category_table.horizontalHeader()
        dh.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 7):
            dh.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        category_layout.addWidget(self.dashboard_category_table)
        outer.addWidget(category_group, 1)

        self.tabs.insertTab(0, self.dashboard_tab, "Gösterge Paneli")
        self.tabs.setCurrentWidget(self.dashboard_tab)

    def _build_context_tab(self):
        self.context_tab = QWidget()
        outer = QVBoxLayout(self.context_tab)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        info = QLabel(
            "Bir çapa kelime/ifadenin hemen öncesindeki veya sonrasındaki sözcükleri sayar. "
            "Örn. ‘koltuk takımı’ + Sol + 1 kelime → model adları; ‘bayi*’ + Sol + 2–3 kelime → bayi/mağaza ifadeleri. "
            "* işareti kök başlangıcı eşleşmesidir. Sonuçlar satış hacmine göre normalize edilmiş arıza oranı değildir."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8;")
        outer.addWidget(info)

        controls_group = QGroupBox("Bağlam sorgusu")
        controls = QGridLayout(controls_group)
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
        self.context_min_count = QSpinBox()
        self.context_min_count.setRange(1, 9999)
        self.context_min_count.setValue(1)
        self.context_top_k = QSpinBox()
        self.context_top_k.setRange(10, 200)
        self.context_top_k.setValue(50)
        self.context_run_button = QPushButton("Bağlamı Analiz Et")
        self.context_run_button.clicked.connect(self.refresh_context_analysis)
        controls.addWidget(QLabel("Çapa ifade"), 0, 0)
        controls.addWidget(self.context_anchor, 0, 1, 1, 3)
        controls.addWidget(QLabel("Yön"), 0, 4)
        controls.addWidget(self.context_direction, 0, 5)
        controls.addWidget(QLabel("Bağlam uzunluğu"), 1, 0)
        controls.addWidget(self.context_window, 1, 1)
        controls.addWidget(QLabel("Min. tekrar"), 1, 2)
        controls.addWidget(self.context_min_count, 1, 3)
        controls.addWidget(QLabel("Maks. sonuç"), 1, 4)
        controls.addWidget(self.context_top_k, 1, 5)
        controls.addWidget(self.context_run_button, 2, 0, 1, 6)
        outer.addWidget(controls_group)

        card_row = QHBoxLayout()
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
        table_group = QGroupBox("Bağlam sonuçları — çift tıklayınca ilişkili şikâyetler açılır")
        table_layout = QVBoxLayout(table_group)
        self.context_table = QTableWidget(0, 5)
        self.context_table.setHorizontalHeaderLabels(
            ["Bağlam", "Geçiş", "Şikâyet", "Çapa İçinde %", "Dönem İçinde %"]
        )
        self.context_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.context_table.setAlternatingRowColors(True)
        self.context_table.cellDoubleClicked.connect(self._open_context_matches)
        ch = self.context_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            ch.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.context_table)
        splitter.addWidget(table_group)
        self.context_chart = HorizontalBarChart("En sık bağlamlar — farklı şikâyet sayısı")
        splitter.addWidget(self.context_chart)
        splitter.setSizes([820, 620])
        outer.addWidget(splitter, 1)

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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mobilitik")
    window = ModernMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
