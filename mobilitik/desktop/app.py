from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QDate, QProcess, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mobilitik.desktop.data import ComplaintRepository


APP_TITLE = "Mobilitik"
DB_PATH = Path("mobilitik.db")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} — Mobilya Şikâyet Analizi")
        self.resize(1280, 820)

        self.repo = ComplaintRepository(DB_PATH)
        self.process: QProcess | None = None

        self._build_ui()
        self.refresh_data()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(self.refresh_data)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QLabel("Mobilitik")
        header.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("Mobilya sektöründeki tüketici şikâyetlerini topla, incele ve dışa aktar.")
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(header)
        layout.addWidget(subtitle)

        controls = QGroupBox("Veri Toplama")
        form = QGridLayout(controls)

        self.company_combo = QComboBox()
        self.company_combo.setEditable(True)
        self.company_combo.addItems(["istikbal", "bellona", "kelebek-mobilya"])
        self.company_combo.setToolTip("Şikayetvar URL'sindeki firma adı (slug).")

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setDate(QDate.currentDate().addYears(-1))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setDate(QDate.currentDate())

        self.max_pages = QSpinBox()
        self.max_pages.setRange(1, 10000)
        self.max_pages.setValue(3)

        self.start_button = QPushButton("Veri Toplamayı Başlat")
        self.start_button.clicked.connect(self.start_scraping)

        self.stop_button = QPushButton("Durdur")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_scraping)

        form.addWidget(QLabel("Firma"), 0, 0)
        form.addWidget(self.company_combo, 0, 1)
        form.addWidget(QLabel("Başlangıç"), 0, 2)
        form.addWidget(self.start_date, 0, 3)
        form.addWidget(QLabel("Bitiş"), 0, 4)
        form.addWidget(self.end_date, 0, 5)
        form.addWidget(QLabel("Maks. sayfa"), 0, 6)
        form.addWidget(self.max_pages, 0, 7)
        form.addWidget(self.start_button, 1, 0, 1, 6)
        form.addWidget(self.stop_button, 1, 6, 1, 2)
        layout.addWidget(controls)

        cards = QHBoxLayout()
        self.total_card = self._metric_card("Toplam Şikâyet", "0")
        self.resolved_card = self._metric_card("Çözüldü", "—")
        self.response_card = self._metric_card("Firma Yanıtı", "—")
        cards.addWidget(self.total_card[0])
        cards.addWidget(self.resolved_card[0])
        cards.addWidget(self.response_card[0])
        layout.addLayout(cards)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Yenile")
        refresh_button.clicked.connect(self.refresh_data)
        export_csv = QPushButton("CSV Dışa Aktar")
        export_csv.clicked.connect(self.export_csv)
        export_xlsx = QPushButton("Excel Dışa Aktar")
        export_xlsx.clicked.connect(self.export_xlsx)
        actions.addWidget(refresh_button)
        actions.addWidget(export_csv)
        actions.addWidget(export_xlsx)
        actions.addStretch()
        layout.addLayout(actions)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Tarih", "Firma", "Başlık", "Çözüldü", "Yanıt", "URL"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        log_group = QGroupBox("Çalışma Günlüğü")
        log_layout = QVBoxLayout(log_group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        log_layout.addWidget(self.log)
        layout.addWidget(log_group)

    def _metric_card(self, title: str, value: str):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        box = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666;")
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: 700;")
        box.addWidget(title_label)
        box.addWidget(value_label)
        return frame, value_label

    def start_scraping(self):
        company = self.company_combo.currentText().strip().strip("/")
        if not company:
            QMessageBox.warning(self, APP_TITLE, "Firma alanı boş bırakılamaz.")
            return

        if self.start_date.date() > self.end_date.date():
            QMessageBox.warning(self, APP_TITLE, "Başlangıç tarihi bitiş tarihinden sonra olamaz.")
            return

        if self.process and self.process.state() != QProcess.NotRunning:
            return

        args = [
            "-m", "scrapy", "crawl", "complaints",
            "-a", f"company={company}",
            "-a", f"start_date={self.start_date.date().toString('yyyy-MM-dd')}",
            "-a", f"end_date={self.end_date.date().toString('yyyy-MM-dd')}",
            "-a", f"max_pages={self.max_pages.value()}",
        ]

        self.process = QProcess(self)
        self.process.setProgram(sys.executable)
        self.process.setArguments(args)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.finished.connect(self._process_finished)

        self.log.append(f"▶ {company} için veri toplama başlatılıyor…")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress.setVisible(True)
        self.refresh_timer.start()
        self.process.start()

    def stop_scraping(self):
        if not self.process or self.process.state() == QProcess.NotRunning:
            return
        self.log.append("■ Durdurma isteği gönderildi.")
        self.process.terminate()
        if not self.process.waitForFinished(2500):
            self.process.kill()

    def _read_process_output(self):
        if not self.process:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if text.strip():
            self.log.append(text.rstrip())

    def _process_finished(self, exit_code: int, _exit_status):
        self.refresh_timer.stop()
        self.progress.setVisible(False)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log.append(f"✓ İşlem tamamlandı. Çıkış kodu: {exit_code}")
        self.refresh_data()

    def refresh_data(self):
        try:
            metrics = self.repo.metrics()
            self.total_card[1].setText(str(metrics["total"]))
            self.resolved_card[1].setText(self._pct(metrics["resolved"], metrics["total"]))
            self.response_card[1].setText(self._pct(metrics["responded"], metrics["total"]))

            rows = self.repo.list_complaints(limit=500)
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [
                    row["complaint_date"] or "",
                    row["company"] or "",
                    row["title"] or "",
                    "Evet" if row["resolved"] else "Hayır",
                    "Evet" if row["company_responded"] else "Hayır",
                    row["complaint_url"] or "",
                ]
                for c, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if c in (3, 4):
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(r, c, item)
        except sqlite3.Error as exc:
            self.log.append(f"Veritabanı uyarısı: {exc}")

    @staticmethod
    def _pct(part: int, total: int) -> str:
        if not total:
            return "—"
        return f"%{(part / total) * 100:.1f}"

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV Kaydet", "mobilitik_export.csv", "CSV (*.csv)")
        if not path:
            return
        self.repo.export_csv(Path(path))
        QMessageBox.information(self, APP_TITLE, f"CSV kaydedildi:\n{path}")

    def export_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "mobilitik_export.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.repo.export_xlsx(Path(path))
        except RuntimeError as exc:
            QMessageBox.critical(self, APP_TITLE, str(exc))
            return
        QMessageBox.information(self, APP_TITLE, f"Excel dosyası kaydedildi:\n{path}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
