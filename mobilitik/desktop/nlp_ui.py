from __future__ import annotations

import html
import sqlite3
import sys

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.analysis.sentiment import (
    ANALYZER_VERSION,
    DEFAULT_MODEL_ID,
    priority_score,
    sentiment_label_tr,
)
from mobilitik.company import normalize_company_input
from mobilitik.desktop.app import APP_TITLE, MainWindow


class NlpMainWindow(MainWindow):
    """Main Mobilitik window with an opt-in NLP analysis workspace."""

    def __init__(self):
        super().__init__()
        self.nlp_store = SentimentStore(self.repo.db_path)
        self.nlp_process: QProcess | None = None
        self.nlp_install_process: QProcess | None = None
        self._nlp_output_buffer = ""
        self._nlp_install_buffer = ""
        self._build_nlp_tab()
        self.refresh_nlp_cached_view()

    def _build_nlp_tab(self):
        self.nlp_tab = QWidget()
        layout = QVBoxLayout(self.nlp_tab)

        info = QLabel(
            "Bu sekme yalnızca siz istediğinizde çalışır. BERTurk modeli uygulama açılırken yüklenmez. "
            "İlk kullanımda NLP bileşenlerini kurun; model ise ilk analiz sırasında Hugging Face'ten indirilir. "
            "Sonuçlar metin hash'i + model + analiz sürümü ile SQLite'ta önbelleğe alınır; değişmeyen şikâyetler yeniden hesaplanmaz. "
            "Hazır model e-ticaret yorumlarında eğitildiği için akademik kullanımda Mobilitik verisi üzerinde ayrıca doğrulama yapılmalıdır."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555;")
        layout.addWidget(info)

        model_group = QGroupBox("İsteğe Bağlı BERTurk Duygu Analizi")
        model_layout = QGridLayout(model_group)
        model_value = QLabel(DEFAULT_MODEL_ID)
        model_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        model_value.setToolTip("3 sınıflı Türkçe BERTurk modeli: Negatif / Nötr / Pozitif")
        self.nlp_install_button = QPushButton("NLP Bileşenlerini Kur / Güncelle")
        self.nlp_install_button.clicked.connect(self.install_nlp_dependencies)
        self.nlp_start_button = QPushButton("Duygu Analizini Başlat")
        self.nlp_start_button.clicked.connect(self.start_nlp_analysis)
        self.nlp_stop_button = QPushButton("Durdur")
        self.nlp_stop_button.setEnabled(False)
        self.nlp_stop_button.clicked.connect(self.stop_nlp_analysis)
        self.nlp_refresh_button = QPushButton("Önbellekteki Sonuçları Yenile")
        self.nlp_refresh_button.clicked.connect(self.refresh_nlp_cached_view)
        model_layout.addWidget(QLabel("Model"), 0, 0)
        model_layout.addWidget(model_value, 0, 1, 1, 3)
        model_layout.addWidget(QLabel("Analiz sürümü"), 1, 0)
        model_layout.addWidget(QLabel(ANALYZER_VERSION), 1, 1)
        model_layout.addWidget(self.nlp_install_button, 2, 0, 1, 2)
        model_layout.addWidget(self.nlp_start_button, 2, 2)
        model_layout.addWidget(self.nlp_stop_button, 2, 3)
        model_layout.addWidget(self.nlp_refresh_button, 3, 0, 1, 4)
        layout.addWidget(model_group)

        self.nlp_progress = QProgressBar()
        self.nlp_progress.setRange(0, 1)
        self.nlp_progress.setValue(0)
        self.nlp_status = QLabel("Hazır — model çalışmıyor.")
        self.nlp_status.setStyleSheet("color: #666;")
        layout.addWidget(self.nlp_progress)
        layout.addWidget(self.nlp_status)

        cards = QHBoxLayout()
        self.nlp_total_card = self._metric_card("Analiz Edilen", "0")
        self.nlp_negative_card = self._metric_card("Negatif", "—")
        self.nlp_neutral_card = self._metric_card("Nötr", "—")
        self.nlp_positive_card = self._metric_card("Pozitif", "—")
        self.nlp_intensity_card = self._metric_card("Ort. Negatiflik", "—")
        for card in (
            self.nlp_total_card,
            self.nlp_negative_card,
            self.nlp_neutral_card,
            self.nlp_positive_card,
            self.nlp_intensity_card,
        ):
            cards.addWidget(card[0])
        layout.addLayout(cards)

        sentiment_group = QGroupBox("Tekil Şikâyet Duygu Sonuçları")
        sentiment_layout = QVBoxLayout(sentiment_group)
        self.nlp_table = QTableWidget(0, 7)
        self.nlp_table.setHorizontalHeaderLabels(
            ["Tarih", "Başlık", "Duygu", "Güven", "Negatif %", "Nötr %", "Pozitif %"]
        )
        self.nlp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nlp_table.setAlternatingRowColors(True)
        header = self.nlp_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        sentiment_layout.addWidget(self.nlp_table)
        layout.addWidget(sentiment_group, 2)

        priority_group = QGroupBox("Kümülatif Aspect Sentiment ve Gelişim Öncelikleri")
        priority_layout = QVBoxLayout(priority_group)
        explanation = QLabel(
            "Şikâyet cümleleri manuel Mobilitik kategorileriyle eşleştirilir ve her kategori için ayrı duygu ortalaması hesaplanır. "
            "Öncelik puanı bir akademik gerçek değil, kullanıcı ağırlıklı karar-destek göstergesidir. Varsayılan: sıklık %40 + negatiflik %35 + çözülmeme %25."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666;")
        priority_layout.addWidget(explanation)

        weights = QHBoxLayout()
        self.frequency_weight = self._weight_spin(40)
        self.negativity_weight = self._weight_spin(35)
        self.unresolved_weight = self._weight_spin(25)
        weights.addWidget(QLabel("Sıklık ağırlığı"))
        weights.addWidget(self.frequency_weight)
        weights.addWidget(QLabel("Negatiflik ağırlığı"))
        weights.addWidget(self.negativity_weight)
        weights.addWidget(QLabel("Çözülmeme ağırlığı"))
        weights.addWidget(self.unresolved_weight)
        recalc = QPushButton("Öncelikleri Yeniden Hesapla")
        recalc.clicked.connect(self.refresh_nlp_cached_view)
        weights.addWidget(recalc)
        weights.addStretch()
        priority_layout.addLayout(weights)

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
        priority_layout.addWidget(self.priority_table)
        layout.addWidget(priority_group, 2)

        log_group = QGroupBox("NLP Günlüğü")
        log_layout = QVBoxLayout(log_group)
        self.nlp_log = QTextEdit()
        self.nlp_log.setReadOnly(True)
        self.nlp_log.setMaximumHeight(150)
        log_layout.addWidget(self.nlp_log)
        layout.addWidget(log_group)

        self.tabs.addTab(self.nlp_tab, "NLP / Duygu Analizi")

    @staticmethod
    def _weight_spin(value: int):
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix(" %")
        return spin

    def _selected_nlp_filter(self):
        company = normalize_company_input(self.company_combo.currentText())
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        return company, start, end

    def install_nlp_dependencies(self):
        if self.nlp_install_process and self.nlp_install_process.state() != QProcess.NotRunning:
            return
        if self.nlp_process and self.nlp_process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, APP_TITLE, "Duygu analizi çalışırken NLP kurulumu yapılamaz.")
            return

        self.nlp_install_process = QProcess(self)
        self.nlp_install_process.setProgram(sys.executable)
        self.nlp_install_process.setArguments(["-m", "mobilitik.nlp_installer"])
        self.nlp_install_process.setProcessChannelMode(QProcess.MergedChannels)
        self.nlp_install_process.readyReadStandardOutput.connect(self._read_nlp_install_output)
        self.nlp_install_process.finished.connect(self._nlp_install_finished)
        self.nlp_install_button.setEnabled(False)
        self.nlp_start_button.setEnabled(False)
        self.nlp_progress.setRange(0, 0)
        self.nlp_status.setText("NLP bileşenleri kuruluyor…")
        self.nlp_log.append("▶ CPU tabanlı PyTorch + Transformers kurulumu başlatıldı.")
        self.nlp_install_process.start()

    def _read_nlp_install_output(self):
        if not self.nlp_install_process:
            return
        text = bytes(self.nlp_install_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if text.strip():
            self.nlp_log.append(text.rstrip())

    def _nlp_install_finished(self, exit_code: int, _status):
        self.nlp_install_button.setEnabled(True)
        self.nlp_start_button.setEnabled(True)
        self.nlp_progress.setRange(0, 1)
        self.nlp_progress.setValue(1 if exit_code == 0 else 0)
        if exit_code == 0:
            self.nlp_status.setText("NLP bileşenleri hazır. Model ilk analizde indirilecek.")
            self.nlp_log.append("✓ NLP bileşenleri başarıyla kuruldu.")
        else:
            self.nlp_status.setText("NLP kurulumu başarısız oldu; günlük ayrıntılarını kontrol edin.")
            self.nlp_log.append(f"✗ NLP kurulumu çıkış kodu: {exit_code}")

    def start_nlp_analysis(self):
        if self.nlp_process and self.nlp_process.state() != QProcess.NotRunning:
            return
        if self.nlp_install_process and self.nlp_install_process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, APP_TITLE, "Önce NLP bileşenlerinin kurulumu tamamlanmalı.")
            return
        try:
            company, start, end = self._selected_nlp_filter()
        except ValueError as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return

        self.nlp_process = QProcess(self)
        self.nlp_process.setProgram(sys.executable)
        self.nlp_process.setArguments(
            [
                "-m",
                "mobilitik.nlp_worker",
                "--db",
                str(self.repo.db_path),
                "--company",
                company,
                "--start-date",
                start,
                "--end-date",
                end,
                "--model",
                DEFAULT_MODEL_ID,
            ]
        )
        self.nlp_process.setProcessChannelMode(QProcess.MergedChannels)
        self.nlp_process.readyReadStandardOutput.connect(self._read_nlp_output)
        self.nlp_process.finished.connect(self._nlp_finished)
        self.nlp_start_button.setEnabled(False)
        self.nlp_install_button.setEnabled(False)
        self.nlp_stop_button.setEnabled(True)
        self.nlp_progress.setRange(0, 0)
        self.nlp_status.setText("BERTurk hazırlanıyor…")
        self.nlp_log.append(f"▶ NLP analizi: {company}, {start}–{end}")
        self.nlp_process.start()

    def _read_nlp_output(self):
        if not self.nlp_process:
            return
        text = bytes(self.nlp_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._nlp_output_buffer += text
        lines = self._nlp_output_buffer.split("\n")
        self._nlp_output_buffer = lines.pop() if lines else ""
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("NLP_PROGRESS "):
                parts = line.split()
                if len(parts) >= 3:
                    done, total = int(parts[1]), int(parts[2])
                    self.nlp_progress.setRange(0, max(1, total))
                    self.nlp_progress.setValue(done)
                    self.nlp_status.setText(f"Duygu analizi: {done} / {total}")
                continue
            if line.startswith("NLP_STATUS "):
                message = line[len("NLP_STATUS "):]
                self.nlp_status.setText(message)
                self.nlp_log.append(message)
                continue
            if line.startswith("NLP_DONE "):
                self.nlp_log.append("✓ NLP analizi tamamlandı.")
                continue
            if line.startswith("NLP_ERROR ") or line.startswith("NLP_WARNING "):
                self.nlp_log.append(line)
                continue
            # Keep relevant model download/runtime lines visible without flooding the main log.
            self.nlp_log.append(line)

    def _nlp_finished(self, exit_code: int, _status):
        self.nlp_start_button.setEnabled(True)
        self.nlp_install_button.setEnabled(True)
        self.nlp_stop_button.setEnabled(False)
        if exit_code == 0:
            self.nlp_status.setText("Analiz tamamlandı; sonuçlar önbelleğe kaydedildi.")
            self.refresh_nlp_cached_view()
        else:
            self.nlp_status.setText("NLP analizi tamamlanamadı; NLP günlüğünü kontrol edin.")
            self.nlp_log.append(f"✗ NLP worker çıkış kodu: {exit_code}")

    def stop_nlp_analysis(self):
        if not self.nlp_process or self.nlp_process.state() == QProcess.NotRunning:
            return
        self.nlp_log.append("■ NLP analizi durduruluyor…")
        self.nlp_process.terminate()
        if not self.nlp_process.waitForFinished(3000):
            self.nlp_process.kill()

    def refresh_nlp_cached_view(self):
        try:
            company, start, end = self._selected_nlp_filter()
            counts = self.nlp_store.counts(
                model_id=DEFAULT_MODEL_ID,
                analyzer_version=ANALYZER_VERSION,
                company=company,
                start_date=start,
                end_date=end,
            )
            rows = list(
                self.nlp_store.complaint_results(
                    model_id=DEFAULT_MODEL_ID,
                    analyzer_version=ANALYZER_VERSION,
                    company=company,
                    start_date=start,
                    end_date=end,
                )
            )
            aspects = list(
                self.nlp_store.aspect_results(
                    model_id=DEFAULT_MODEL_ID,
                    analyzer_version=ANALYZER_VERSION,
                    company=company,
                    start_date=start,
                    end_date=end,
                )
            )
        except (sqlite3.Error, ValueError) as exc:
            self.nlp_log.append(f"NLP önbellek uyarısı: {exc}")
            return

        total = int(counts["total"])
        self.nlp_total_card[1].setText(str(total))
        self.nlp_negative_card[1].setText(self._pct(int(counts["negative"]), total))
        self.nlp_neutral_card[1].setText(self._pct(int(counts["neutral"]), total))
        self.nlp_positive_card[1].setText(self._pct(int(counts["positive"]), total))
        self.nlp_intensity_card[1].setText(f"%{float(counts['mean_negative']) * 100:.1f}" if total else "—")

        self.nlp_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            tooltip = (row["complaint_text"] or "")[:3000]
            values = [
                row["complaint_date"] or "",
                row["title"] or "",
                sentiment_label_tr(row["label"]),
                f"%{float(row['confidence']) * 100:.1f}",
                f"%{float(row['negative']) * 100:.1f}",
                f"%{float(row['neutral']) * 100:.1f}",
                f"%{float(row['positive']) * 100:.1f}",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c == 1:
                    item.setToolTip(tooltip)
                if c >= 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.nlp_table.setItem(r, c, item)

        fw = self.frequency_weight.value()
        nw = self.negativity_weight.value()
        uw = self.unresolved_weight.value()
        priority_rows = []
        for row in aspects:
            issue_share = (int(row["complaints"]) / total) if total else 0.0
            score = priority_score(
                issue_share,
                float(row["mean_negative"] or 0.0),
                float(row["unresolved_rate"] or 0.0),
                frequency_weight=fw,
                negativity_weight=nw,
                unresolved_weight=uw,
            )
            priority_rows.append((score, row, issue_share))
        priority_rows.sort(key=lambda item: (-item[0], item[1]["category"]))

        self.priority_table.setRowCount(len(priority_rows))
        for r, (score, row, issue_share) in enumerate(priority_rows):
            values = [
                row["category"],
                row["complaints"],
                f"%{issue_share * 100:.1f}",
                f"%{float(row['mean_negative'] or 0.0) * 100:.1f}",
                f"%{float(row['high_negative_rate'] or 0.0) * 100:.1f}",
                f"%{float(row['unresolved_rate'] or 0.0) * 100:.1f}",
                self._duration(row["mean_response_hours"]),
                f"{score:.1f}",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.priority_table.setItem(r, c, item)

        if total:
            self.nlp_status.setText(
                f"Önbellekte {total} NLP sonucu gösteriliyor. Yeni analiz yalnızca eksik/değişmiş kayıtları işler."
            )
        else:
            self.nlp_status.setText("Bu firma/dönem için henüz NLP sonucu yok. Model otomatik çalıştırılmadı.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = NlpMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
