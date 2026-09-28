from __future__ import annotations

import html
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
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.category_terms import category_distinctive_terms
from mobilitik.analysis.classifier import (
    classify_record,
    format_rule_terms,
    get_category_rules,
    parse_rule_terms,
    reset_category_rules,
    set_category_rules,
)
from mobilitik.analysis.summary import category_summary
from mobilitik.analysis.textstats import TextAnalyzer, normalize_text
from mobilitik.analysis.verbs import progressive_verb_stats
from mobilitik.desktop.commands import build_scrapy_args
from mobilitik.desktop.data import ComplaintRepository


APP_TITLE = "Mobilitik"
DB_PATH = Path("mobilitik.db")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} — Mobilya Şikâyet Analizi")
        self.resize(1420, 980)
        self.repo = ComplaintRepository(DB_PATH)
        self.process: QProcess | None = None
        self._analysis_records: list[dict] = []
        self._distinctive_cache: dict[str, list] = {}
        self._verb_cache = []
        self._build_ui()
        self._load_category_editor()
        self._refresh_category_choices()
        self.refresh_analysis()
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
        subtitle = QLabel(
            "Mobilya sektöründeki tüketici şikâyetlerini topla, sınıflandır ve çözüm performansını incele."
        )
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(header)
        layout.addWidget(subtitle)

        controls = QGroupBox("Veri Toplama ve Analiz Filtresi")
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
        self.analyze_button = QPushButton("Filtreyi Uygula ve Analiz Et")
        self.analyze_button.setToolTip(
            "Firma ve tarih aralığını Şikâyetler dahil bütün analiz sekmelerine uygular."
        )
        self.analyze_button.clicked.connect(self.refresh_analysis)

        form.addWidget(QLabel("Firma"), 0, 0)
        form.addWidget(self.company_combo, 0, 1)
        form.addWidget(QLabel("Başlangıç"), 0, 2)
        form.addWidget(self.start_date, 0, 3)
        form.addWidget(QLabel("Bitiş"), 0, 4)
        form.addWidget(self.end_date, 0, 5)
        form.addWidget(QLabel("Maks. sayfa"), 0, 6)
        form.addWidget(self.max_pages, 0, 7)
        form.addWidget(self.start_button, 1, 0, 1, 4)
        form.addWidget(self.stop_button, 1, 4, 1, 2)
        form.addWidget(self.analyze_button, 1, 6, 1, 2)
        layout.addWidget(controls)

        cards = QHBoxLayout()
        self.total_card = self._metric_card("Seçili Dönem Şikâyet", "0")
        self.resolved_card = self._metric_card("Çözüldü", "—")
        self.response_card = self._metric_card("Firma Yanıtı", "—")
        self.response_time_card = self._metric_card("Medyan Yanıt Süresi", "—")
        self.resolution_time_card = self._metric_card("Medyan Çözüm Süresi", "—")
        cards.addWidget(self.total_card[0])
        cards.addWidget(self.resolved_card[0])
        cards.addWidget(self.response_card[0])
        cards.addWidget(self.response_time_card[0])
        cards.addWidget(self.resolution_time_card[0])
        layout.addLayout(cards)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Yenile / Filtreyi Uygula")
        refresh_button.clicked.connect(self.refresh_analysis)
        export_csv = QPushButton("CSV Dışa Aktar")
        export_csv.clicked.connect(self.export_csv)
        export_xlsx = QPushButton("Excel Dışa Aktar")
        export_xlsx.clicked.connect(self.export_xlsx)
        actions.addWidget(refresh_button)
        actions.addWidget(export_csv)
        actions.addWidget(export_xlsx)
        actions.addStretch()
        layout.addLayout(actions)

        tabs = QTabWidget()
        self.tabs = tabs

        # Complaints tab -------------------------------------------------
        self.complaints_tab = QWidget()
        complaints_layout = QVBoxLayout(self.complaints_tab)
        complaint_filter_row = QHBoxLayout()
        self.complaint_category_combo = QComboBox()
        self.complaint_category_combo.currentIndexChanged.connect(
            lambda *_: self._render_complaints(self._analysis_records)
        )
        complaint_filter_row.addWidget(QLabel("Kategori filtresi"))
        complaint_filter_row.addWidget(self.complaint_category_combo)
        complaint_filter_row.addStretch()
        complaints_layout.addLayout(complaint_filter_row)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Firma", "Başlık", "Çözüldü", "Yanıt", "Yanıt Süresi", "Çözüm Süresi", "URL"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (3, 4, 5, 6):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        complaints_layout.addWidget(self.table)
        tabs.addTab(self.complaints_tab, "Şikâyetler")

        # Category analysis tab -----------------------------------------
        self.analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(self.analysis_tab)
        analysis_info = QLabel(
            "Kategoriler Şikayetvar'dan alınmaz. Mobilitik'teki manuel anahtar kelime/ifade kurallarına göre hesaplanır ve 'Kategori Yönetimi' sekmesinden değiştirilebilir. "
            "Bir şikâyet birden fazla kategoriye girebilir. 'Tümü' satırı seçili dönemdeki bütün şikâyetleri tek kez sayar."
        )
        analysis_info.setWordWrap(True)
        analysis_info.setStyleSheet("color: #666;")
        analysis_layout.addWidget(analysis_info)
        self.category_table = QTableWidget(0, 7)
        self.category_table.setHorizontalHeaderLabels(
            [
                "Kategori",
                "Şikâyet",
                "Çözülen",
                "Çözülme %",
                "Firma Yanıt %",
                "Medyan Yanıt",
                "Medyan Çözüm",
            ]
        )
        self.category_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.category_table.setAlternatingRowColors(True)
        category_header = self.category_table.horizontalHeader()
        category_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            category_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        analysis_layout.addWidget(self.category_table)
        tabs.addTab(self.analysis_tab, "Kategori Analizi")

        # Word analysis tab ---------------------------------------------
        self.word_tab = QWidget()
        word_layout = QVBoxLayout(self.word_tab)
        word_info = QLabel(
            "Seçili firma ve tarih aralığındaki şikâyet metinlerinden en sık kelime ve kelime grupları ile TF-IDF ağırlıklı ifadeler hesaplanır. Türkçe karakterler korunur."
        )
        word_info.setWordWrap(True)
        word_info.setStyleSheet("color: #666;")
        word_layout.addWidget(word_info)
        word_controls = QHBoxLayout()
        self.ngram_combo = QComboBox()
        self.ngram_combo.addItem("Tek kelime", 1)
        self.ngram_combo.addItem("İki kelime", 2)
        self.ngram_combo.addItem("Üç kelime", 3)
        self.ngram_combo.currentIndexChanged.connect(self.refresh_word_analysis)
        word_controls.addWidget(QLabel("İfade uzunluğu"))
        word_controls.addWidget(self.ngram_combo)
        word_controls.addStretch()
        word_layout.addLayout(word_controls)
        self.word_table = QTableWidget(0, 4)
        self.word_table.setHorizontalHeaderLabels(["İfade", "Sıklık", "TF-IDF", "Belge Sayısı"])
        self.word_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.word_table.setAlternatingRowColors(True)
        word_header = self.word_table.horizontalHeader()
        word_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 4):
            word_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        word_layout.addWidget(self.word_table)
        tabs.addTab(self.word_tab, "Kelime Analizi")

        # Verb analysis tab ---------------------------------------------
        self.verb_tab = QWidget()
        verb_layout = QVBoxLayout(self.verb_tab)
        verb_info = QLabel(
            "-ıyor / -iyor / -uyor / -üyor biçimindeki fiiller taranır. Gösterilen değer tam dilbilimsel kök değil, şeffaf bir yaklaşık fiil gövdesidir; örnek çekimli biçimler yanında gösterilir."
        )
        verb_info.setWordWrap(True)
        verb_info.setStyleSheet("color: #666;")
        verb_layout.addWidget(verb_info)
        verb_controls = QHBoxLayout()
        self.verb_filter = QLineEdit()
        self.verb_filter.setPlaceholderText("Fiil gövdesinde veya örnek biçimde ara…")
        self.verb_filter.textChanged.connect(lambda *_: self._render_verb_analysis())
        verb_controls.addWidget(QLabel("Fiil filtresi"))
        verb_controls.addWidget(self.verb_filter)
        verb_layout.addLayout(verb_controls)
        self.verb_table = QTableWidget(0, 4)
        self.verb_table.setHorizontalHeaderLabels(
            ["Yaklaşık Gövde", "Örnek Çekimli Biçimler", "Sıklık", "Belge Sayısı"]
        )
        self.verb_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verb_table.setAlternatingRowColors(True)
        verb_header = self.verb_table.horizontalHeader()
        verb_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        verb_header.setSectionResizeMode(1, QHeaderView.Stretch)
        verb_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        verb_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        verb_layout.addWidget(self.verb_table)
        tabs.addTab(self.verb_tab, "Fiil Analizi")

        # Distinctive category terms tab --------------------------------
        self.distinctive_tab = QWidget()
        distinctive_layout = QVBoxLayout(self.distinctive_tab)
        distinctive_info = QLabel(
            "Kategoriye özgü ayırt edici ifadeler gösterilir. 'Tümü' seçeneği seçili dönemin bütün kayıtlarında öne çıkan ifadeleri birlikte gösterir."
        )
        distinctive_info.setWordWrap(True)
        distinctive_info.setStyleSheet("color: #666;")
        distinctive_layout.addWidget(distinctive_info)
        distinctive_controls = QHBoxLayout()
        self.distinctive_category_combo = QComboBox()
        self.distinctive_category_combo.currentIndexChanged.connect(self._render_distinctive_category)
        self.distinctive_ngram_combo = QComboBox()
        self.distinctive_ngram_combo.addItem("Tek kelime", 1)
        self.distinctive_ngram_combo.addItem("İki kelime", 2)
        self.distinctive_ngram_combo.addItem("Üç kelime", 3)
        self.distinctive_ngram_combo.setCurrentIndex(1)
        self.distinctive_ngram_combo.currentIndexChanged.connect(self.refresh_distinctive_analysis)
        distinctive_controls.addWidget(QLabel("Kategori"))
        distinctive_controls.addWidget(self.distinctive_category_combo)
        distinctive_controls.addWidget(QLabel("İfade uzunluğu"))
        distinctive_controls.addWidget(self.distinctive_ngram_combo)
        distinctive_controls.addStretch()
        distinctive_layout.addLayout(distinctive_controls)
        self.distinctive_table = QTableWidget(0, 3)
        self.distinctive_table.setHorizontalHeaderLabels(["İfade", "Skor", "Sıklık"])
        self.distinctive_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.distinctive_table.setAlternatingRowColors(True)
        distinctive_header = self.distinctive_table.horizontalHeader()
        distinctive_header.setSectionResizeMode(0, QHeaderView.Stretch)
        distinctive_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        distinctive_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        distinctive_layout.addWidget(self.distinctive_table)
        tabs.addTab(self.distinctive_tab, "Kategori İfadeleri")

        # Manual category editor tab ------------------------------------
        self.category_editor_tab = QWidget()
        category_editor_layout = QVBoxLayout(self.category_editor_tab)
        category_editor_info = QLabel(
            "Kategorileri siz tanımlarsınız. İfadeleri noktalı virgülle ayırın. İsterseniz ağırlık verin: teslimat=3; teslim edilmedi=4. Ağırlık yazılmazsa 2 kullanılır ve tek eşleşme kategoriyi etkinleştirir."
        )
        category_editor_info.setWordWrap(True)
        category_editor_info.setStyleSheet("color: #666;")
        category_editor_layout.addWidget(category_editor_info)
        self.category_editor = QTableWidget(0, 2)
        self.category_editor.setHorizontalHeaderLabels(["Kategori Adı", "Anahtar Kelime / İfadeler"])
        editor_header = self.category_editor.horizontalHeader()
        editor_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        editor_header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.category_editor.setAlternatingRowColors(True)
        category_editor_layout.addWidget(self.category_editor)
        category_buttons = QHBoxLayout()
        add_category = QPushButton("Yeni Kategori")
        add_category.clicked.connect(self._add_category_row)
        delete_category = QPushButton("Seçili Kategoriyi Sil")
        delete_category.clicked.connect(self._delete_selected_category)
        save_categories = QPushButton("Kategorileri Kaydet ve Analizi Yenile")
        save_categories.clicked.connect(self._save_category_editor)
        reset_categories = QPushButton("Varsayılan Kategorilere Dön")
        reset_categories.clicked.connect(self._reset_categories)
        category_buttons.addWidget(add_category)
        category_buttons.addWidget(delete_category)
        category_buttons.addWidget(save_categories)
        category_buttons.addWidget(reset_categories)
        category_buttons.addStretch()
        category_editor_layout.addLayout(category_buttons)
        tabs.addTab(self.category_editor_tab, "Kategori Yönetimi")

        layout.addWidget(tabs, 1)
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

        try:
            args = build_scrapy_args(
                company,
                self.start_date.date().toString("yyyy-MM-dd"),
                self.end_date.date().toString("yyyy-MM-dd"),
                self.max_pages.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))
            return

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
        self.refresh_analysis()

    def _filtered_records(self):
        company = self.company_combo.currentText().strip().strip("/")
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        rows = self.repo.filtered_complaints(company=company, start_date=start, end_date=end)
        return company, start, end, [dict(row) for row in rows]

    def refresh_data(self):
        """Refresh only the complaint list while a crawl is running."""
        try:
            _company, _start, _end, records = self._filtered_records()
            self._analysis_records = records
            self._render_complaints(records)
        except sqlite3.Error as exc:
            self.log.append(f"Veritabanı uyarısı: {exc}")

    def _records_for_selected_category(self, records: list[dict]) -> list[dict]:
        category = self.complaint_category_combo.currentText() or "Tümü"
        if category == "Tümü":
            return records
        selected: list[dict] = []
        for record in records:
            result = classify_record(record.get("title"), record.get("complaint_text"))
            categories = result.categories or ["Diğer"]
            if category in categories:
                selected.append(record)
        return selected

    @staticmethod
    def _tooltip_text(record: dict) -> str:
        text = (record.get("complaint_text") or "").strip()
        if not text:
            return "Şikâyet metni bulunamadı."
        return text[:3000] + ("…" if len(text) > 3000 else "")

    def _render_complaints(self, records: list[dict] | None = None):
        records = records if records is not None else self._analysis_records
        visible = self._records_for_selected_category(records)
        self.table.setRowCount(len(visible))
        for r, row in enumerate(visible):
            tooltip = self._tooltip_text(row)
            values = [
                row.get("complaint_date") or "",
                row.get("company") or "",
                row.get("title") or "",
                "Evet" if row.get("resolved") else "Hayır",
                "Evet" if row.get("company_responded") else "Hayır",
                self._duration(row.get("response_hours")),
                self._duration(row.get("resolution_hours")),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignCenter)
                if c == 2:
                    item.setToolTip(tooltip)
                self.table.setItem(r, c, item)

            url = row.get("complaint_url") or ""
            url_label = QLabel()
            if url:
                safe_url = html.escape(url, quote=True)
                url_label.setText(f'<a href="{safe_url}">Şikâyeti aç ↗</a>')
                url_label.setOpenExternalLinks(True)
                url_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                url_label.setToolTip(tooltip)
            else:
                url_label.setText("—")
            self.table.setCellWidget(r, 7, url_label)

    def refresh_analysis(self):
        try:
            company, start, end, records = self._filtered_records()
            self._analysis_records = records
            metrics = self.repo.filtered_metrics(company=company, start_date=start, end_date=end)
            self.total_card[1].setText(str(metrics["total"]))
            self.resolved_card[1].setText(self._pct(metrics["resolved"], metrics["total"]))
            self.response_card[1].setText(self._pct(metrics["responded"], metrics["total"]))
            self.response_time_card[1].setText(self._duration(metrics["median_response_hours"]))
            self.resolution_time_card[1].setText(self._duration(metrics["median_resolution_hours"]))
            self.response_time_card[0].setToolTip(
                f"Açık yanıt tarihi bulunan {metrics['timed_responses']} kaydın medyanı."
            )
            self.resolution_time_card[0].setToolTip(
                f"Açık çözüm tarihi bulunan {metrics['timed_resolutions']} kaydın medyanı."
            )

            self._refresh_category_choices()
            self._render_complaints(records)

            summary = category_summary(records)
            self.category_table.setRowCount(len(summary))
            for r, item in enumerate(summary):
                values = [
                    item["category"],
                    item["complaints"],
                    item["resolved"],
                    f"%{item['resolved_rate']:.1f}",
                    f"%{item['response_rate']:.1f}",
                    self._duration(item["median_response_hours"]),
                    self._duration(item["median_resolution_hours"]),
                ]
                for c, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if c > 0:
                        cell.setTextAlignment(Qt.AlignCenter)
                    self.category_table.setItem(r, c, cell)

            self.refresh_word_analysis(records=records)
            self.refresh_verb_analysis(records=records)
            self.refresh_distinctive_analysis(records=records)
            self.log.append(f"Analiz güncellendi: {company}, {start}–{end}, {len(records)} kayıt.")
        except sqlite3.Error as exc:
            self.log.append(f"Analiz veritabanı uyarısı: {exc}")

    def refresh_word_analysis(self, *_args, records=None):
        try:
            if records is None:
                records = self._analysis_records or self._filtered_records()[3]
            documents = [f"{r.get('title') or ''} {r.get('complaint_text') or ''}" for r in records]
            analyzer = TextAnalyzer(documents)
            n = int(self.ngram_combo.currentData() or 1)
            frequencies = dict(analyzer.top_ngrams(n=n, top_k=50))
            tfidf_rows = analyzer.tfidf(n=n, top_k=50, min_doc_freq=1)
            tfidf_map = {row.term: row.score for row in tfidf_rows}
            doc_freq = analyzer.document_frequency(n=n)
            terms = sorted(frequencies, key=lambda term: frequencies[term], reverse=True)[:50]
            self.word_table.setRowCount(len(terms))
            for r, term in enumerate(terms):
                values = [
                    term,
                    frequencies.get(term, 0),
                    f"{tfidf_map.get(term, 0.0):.2f}",
                    doc_freq.get(term, 0),
                ]
                for c, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if c > 0:
                        cell.setTextAlignment(Qt.AlignCenter)
                    self.word_table.setItem(r, c, cell)
        except sqlite3.Error as exc:
            self.log.append(f"Kelime analizi veritabanı uyarısı: {exc}")

    def refresh_verb_analysis(self, *_args, records=None):
        if records is None:
            records = self._analysis_records or self._filtered_records()[3]
        documents = [f"{r.get('title') or ''} {r.get('complaint_text') or ''}" for r in records]
        self._verb_cache = progressive_verb_stats(documents, top_k=200)
        self._render_verb_analysis()

    def _render_verb_analysis(self):
        query = normalize_text(self.verb_filter.text()).strip()
        rows = []
        for item in self._verb_cache:
            searchable = normalize_text(f"{item.stem} {' '.join(item.examples)}")
            if query and query not in searchable:
                continue
            rows.append(item)
        self.verb_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [item.stem, ", ".join(item.examples), item.count, item.document_count]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if c >= 2:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.verb_table.setItem(r, c, cell)

    def refresh_distinctive_analysis(self, *_args, records=None):
        try:
            if records is None:
                records = self._analysis_records or self._filtered_records()[3]
            n = int(self.distinctive_ngram_combo.currentData() or 2)
            current_category = self.distinctive_category_combo.currentText() or "Tümü"
            self._distinctive_cache = category_distinctive_terms(records, n=n, top_k=30)

            self.distinctive_category_combo.blockSignals(True)
            self.distinctive_category_combo.clear()
            categories = list(self._distinctive_cache)
            if "Tümü" in categories:
                categories = ["Tümü"] + sorted(category for category in categories if category != "Tümü")
            self.distinctive_category_combo.addItems(categories)
            if current_category in categories:
                self.distinctive_category_combo.setCurrentText(current_category)
            elif "Tümü" in categories:
                self.distinctive_category_combo.setCurrentText("Tümü")
            self.distinctive_category_combo.blockSignals(False)
            self._render_distinctive_category()
        except sqlite3.Error as exc:
            self.log.append(f"Kategori ifade analizi veritabanı uyarısı: {exc}")

    def _render_distinctive_category(self, *_args):
        category = self.distinctive_category_combo.currentText()
        rows = self._distinctive_cache.get(category, [])
        self.distinctive_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [item.term, f"{item.score:.2f}", item.count]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if c > 0:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.distinctive_table.setItem(r, c, cell)

    def _refresh_category_choices(self):
        current = self.complaint_category_combo.currentText() if hasattr(self, "complaint_category_combo") else "Tümü"
        categories = ["Tümü", *sorted(get_category_rules()), "Diğer"]
        if not hasattr(self, "complaint_category_combo"):
            return
        self.complaint_category_combo.blockSignals(True)
        self.complaint_category_combo.clear()
        self.complaint_category_combo.addItems(categories)
        self.complaint_category_combo.setCurrentText(current if current in categories else "Tümü")
        self.complaint_category_combo.blockSignals(False)

    def _load_category_editor(self):
        rules = get_category_rules()
        self.category_editor.setRowCount(len(rules))
        for row_index, (category, terms) in enumerate(rules.items()):
            self.category_editor.setItem(row_index, 0, QTableWidgetItem(category))
            self.category_editor.setItem(row_index, 1, QTableWidgetItem(format_rule_terms(terms)))

    def _add_category_row(self):
        row = self.category_editor.rowCount()
        self.category_editor.insertRow(row)
        self.category_editor.setItem(row, 0, QTableWidgetItem("Yeni Kategori"))
        self.category_editor.setItem(row, 1, QTableWidgetItem("anahtar ifade=2"))
        self.category_editor.setCurrentCell(row, 0)

    def _delete_selected_category(self):
        rows = sorted({index.row() for index in self.category_editor.selectedIndexes()}, reverse=True)
        if not rows and self.category_editor.currentRow() >= 0:
            rows = [self.category_editor.currentRow()]
        for row in rows:
            self.category_editor.removeRow(row)

    def _save_category_editor(self):
        rules: dict[str, dict[str, float]] = {}
        try:
            for row in range(self.category_editor.rowCount()):
                category_item = self.category_editor.item(row, 0)
                terms_item = self.category_editor.item(row, 1)
                category = category_item.text().strip() if category_item else ""
                term_text = terms_item.text().strip() if terms_item else ""
                if not category and not term_text:
                    continue
                if not category:
                    raise ValueError(f"{row + 1}. satırda kategori adı boş.")
                terms = parse_rule_terms(term_text)
                if not terms:
                    raise ValueError(f"'{category}' kategorisinde en az bir ifade olmalı.")
                rules[category] = terms
            set_category_rules(rules, persist=True)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, APP_TITLE, f"Kategori kuralları kaydedilemedi:\n{exc}")
            return
        self._refresh_category_choices()
        self.refresh_analysis()
        self.log.append("Manuel kategori kuralları kaydedildi ve analiz yenilendi.")

    def _reset_categories(self):
        try:
            reset_category_rules(persist=True)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, f"Varsayılan kategoriler kaydedilemedi:\n{exc}")
            return
        self._load_category_editor()
        self._refresh_category_choices()
        self.refresh_analysis()
        self.log.append("Kategori kuralları varsayılan değerlere döndürüldü.")

    @staticmethod
    def _pct(part: int, total: int) -> str:
        if not total:
            return "—"
        return f"%{(part / total) * 100:.1f}"

    @staticmethod
    def _duration(hours) -> str:
        if hours is None:
            return "—"
        hours = float(hours)
        if hours < 24:
            return f"{hours:.1f} sa"
        return f"{hours / 24.0:.1f} gün"

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
