from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.classifier import classify_record
from mobilitik.analysis.sentiment import ANALYZER_VERSION, DEFAULT_MODEL_ID
from mobilitik.analysis.verbs import DEFAULT_VERB_SUFFIXES, parse_suffix_conditions, suffix_verb_stats
from mobilitik.desktop.app import APP_TITLE
from mobilitik.desktop.drilldown import ComplaintDrilldownDialog, record_text
from mobilitik.desktop.enhanced_ui import EnhancedMainWindow


class AdvancedMainWindow(EnhancedMainWindow):
    """Research-oriented UI additions layered on the stable Mobilitik window."""

    def __init__(self):
        self._open_drilldown_dialogs: list[ComplaintDrilldownDialog] = []
        super().__init__()
        self._setup_word_drilldown()
        self._setup_category_drilldown()
        self._setup_verb_conditions()
        self._setup_nlp_details()
        self.refresh_analysis()
        self.refresh_nlp_cached_view()

    # ------------------------------------------------------------------
    # Better complaint-text fallbacks
    # ------------------------------------------------------------------
    @staticmethod
    def _tooltip_text(record: dict) -> str:
        text = record_text(record)
        return text[:3000] + ("…" if len(text) > 3000 else "")

    def _show_distinctive_matches_for_term(self, term: str):
        super()._show_distinctive_matches_for_term(term)
        if not hasattr(self, "distinctive_match_table"):
            return
        for row, record in enumerate(getattr(self, "_distinctive_match_records", [])):
            text = record_text(record)
            item = QTableWidgetItem(text)
            item.setToolTip(text[:3000])
            self.distinctive_match_table.setItem(row, 2, item)

    def _show_distinctive_match_preview(self, row: int, _column: int = 0):
        records = getattr(self, "_distinctive_match_records", [])
        if row < 0 or row >= len(records):
            return
        record = records[row]
        title = record.get("title") or "Başlıksız şikâyet"
        self.distinctive_preview.setPlainText(f"{title}\n\n{record_text(record)}")

    # ------------------------------------------------------------------
    # Shared drill-down windows
    # ------------------------------------------------------------------
    def _open_records_dialog(self, title: str, records: list[dict]):
        dialog = ComplaintDrilldownDialog(title, records, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._open_drilldown_dialogs.append(dialog)

        def cleanup(*_args):
            if dialog in self._open_drilldown_dialogs:
                self._open_drilldown_dialogs.remove(dialog)

        dialog.destroyed.connect(cleanup)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _setup_word_drilldown(self):
        self.word_table.cellDoubleClicked.connect(self._open_word_matches)
        self.word_table.setToolTip("Bir ifadeye çift tıklayarak ilişkili şikâyetleri açın.")

    def _open_word_matches(self, row: int, _column: int = 0):
        item = self.word_table.item(row, 0)
        if item is None:
            return
        term = item.text()
        matches = [
            record for record in getattr(self, "_analysis_records", [])
            if self._record_contains_term(record, term)
        ]
        self._open_records_dialog(f"Kelime / İfade: {term}", matches)

    def _setup_category_drilldown(self):
        self.category_table.cellClicked.connect(self._open_category_matches)
        self.category_table.setToolTip(
            "Şikâyet sayısına tıklayarak o kategoriye giren kayıtları ayrı pencerede açın."
        )

    def _records_for_category(self, category: str) -> list[dict]:
        records = list(getattr(self, "_analysis_records", []))
        if category == "Tümü":
            return records
        matches: list[dict] = []
        for record in records:
            result = classify_record(record.get("title"), record.get("complaint_text"))
            categories = result.categories or ["Diğer"]
            if category in categories:
                matches.append(record)
        return matches

    def _open_category_matches(self, row: int, column: int):
        if column != 1:
            return
        item = self.category_table.item(row, 0)
        if item is None:
            return
        category = item.text()
        self._open_records_dialog(
            f"Kategori: {category}",
            self._records_for_category(category),
        )

    # ------------------------------------------------------------------
    # Configurable verb/suffix analysis
    # ------------------------------------------------------------------
    def _setup_verb_conditions(self):
        layout = self.verb_tab.layout()
        if layout is None:
            return
        row = QHBoxLayout()
        self.verb_suffix_input = QLineEdit()
        self.verb_suffix_input.setText("; ".join(DEFAULT_VERB_SUFFIXES))
        self.verb_suffix_input.setPlaceholderText("Örn: ıyor; iyor; uyor; üyor; ıldı; ildi; uldu; üldü")
        self.verb_suffix_input.setToolTip(
            "Noktalı virgül veya virgülle ayırın. Başındaki '-' işareti isteğe bağlıdır."
        )
        apply_button = QPushButton("Koşulları Uygula")
        apply_button.clicked.connect(self.refresh_verb_analysis)
        add_passive = QPushButton("-ıldı/-ildi Grubunu Ekle")
        add_passive.clicked.connect(self._add_passive_suffixes)
        row.addWidget(QLabel("Taranacak fiil son ekleri"))
        row.addWidget(self.verb_suffix_input, 1)
        row.addWidget(apply_button)
        row.addWidget(add_passive)
        layout.insertLayout(1, row)
        self.verb_suffix_input.returnPressed.connect(self.refresh_verb_analysis)

    def _add_passive_suffixes(self):
        current = list(parse_suffix_conditions(self.verb_suffix_input.text()))
        for suffix in ("ıldı", "ildi", "uldu", "üldü"):
            if suffix not in current:
                current.append(suffix)
        self.verb_suffix_input.setText("; ".join(current))
        self.refresh_verb_analysis()

    def refresh_verb_analysis(self, *_args, records=None):
        if records is None:
            records = getattr(self, "_analysis_records", [])
            if not records and hasattr(self, "_filtered_records"):
                records = self._filtered_records()[3]
        documents = [f"{r.get('title') or ''} {r.get('complaint_text') or ''}" for r in records]
        suffixes = (
            self.verb_suffix_input.text()
            if hasattr(self, "verb_suffix_input")
            else DEFAULT_VERB_SUFFIXES
        )
        self._verb_cache = suffix_verb_stats(documents, suffixes=suffixes, top_k=200)
        if hasattr(self, "verb_table"):
            self._render_verb_analysis()

    # ------------------------------------------------------------------
    # Detailed NLP statistics
    # ------------------------------------------------------------------
    def _setup_nlp_details(self):
        self.nlp_detail_page = QWidget()
        layout = QVBoxLayout(self.nlp_detail_page)
        info = QLabel(
            "Bu bölüm önbellekteki BERTurk sonuçlarını daha ayrıntılı özetler. "
            "Model güveni, olasılık dağılımları ve aspect duygu değerleri yorum yardımcısıdır; "
            "akademik kullanımda manuel doğrulama örneklemiyle raporlanmalıdır."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        splitter = QSplitter(Qt.Vertical)

        summary_group = QGroupBox("Genel Duygu İstatistikleri")
        summary_layout = QVBoxLayout(summary_group)
        self.nlp_detail_summary = QTableWidget(0, 2)
        self.nlp_detail_summary.setHorizontalHeaderLabels(["Gösterge", "Değer"])
        self.nlp_detail_summary.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nlp_detail_summary.setAlternatingRowColors(True)
        self.nlp_detail_summary.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.nlp_detail_summary.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        summary_layout.addWidget(self.nlp_detail_summary)
        splitter.addWidget(summary_group)

        aspect_group = QGroupBox("Kategori Bazlı Aspect Duygu Dağılımı")
        aspect_layout = QVBoxLayout(aspect_group)
        self.nlp_aspect_detail_table = QTableWidget(0, 8)
        self.nlp_aspect_detail_table.setHorizontalHeaderLabels(
            ["Kategori", "Şikâyet", "Cümle", "Negatif %", "Nötr %", "Pozitif %", "Çözülmeme %", "Ort. Yanıt"]
        )
        self.nlp_aspect_detail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nlp_aspect_detail_table.setAlternatingRowColors(True)
        ah = self.nlp_aspect_detail_table.horizontalHeader()
        ah.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 8):
            ah.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        aspect_layout.addWidget(self.nlp_aspect_detail_table)
        splitter.addWidget(aspect_group)

        uncertain_group = QGroupBox("Düşük Güvenli / Manuel Kontrole Uygun Kayıtlar")
        uncertain_layout = QVBoxLayout(uncertain_group)
        self.nlp_uncertain_table = QTableWidget(0, 6)
        self.nlp_uncertain_table.setHorizontalHeaderLabels(
            ["Tarih", "Başlık", "Etiket", "Güven %", "Negatif %", "Pozitif %"]
        )
        self.nlp_uncertain_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nlp_uncertain_table.setAlternatingRowColors(True)
        uh = self.nlp_uncertain_table.horizontalHeader()
        uh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        uh.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 6):
            uh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        uncertain_layout.addWidget(self.nlp_uncertain_table)
        splitter.addWidget(uncertain_group)

        splitter.setSizes([230, 300, 260])
        layout.addWidget(splitter, 1)
        self.nlp_inner_tabs.addTab(self.nlp_detail_page, "Detaylı İstatistikler")

    @staticmethod
    def _mean(rows, key: str, predicate=None):
        selected = [row for row in rows if predicate is None or predicate(row)]
        if not selected:
            return None
        return sum(float(row[key] or 0.0) for row in selected) / len(selected)

    @staticmethod
    def _format_pct(value):
        return "—" if value is None else f"%{float(value) * 100:.1f}"

    def refresh_nlp_cached_view(self):
        super().refresh_nlp_cached_view()
        if not hasattr(self, "nlp_detail_summary") or not hasattr(self, "nlp_store"):
            return
        try:
            company, start, end = self._selected_nlp_filter()
            rows = list(self.nlp_store.complaint_results(
                model_id=DEFAULT_MODEL_ID,
                analyzer_version=ANALYZER_VERSION,
                company=company,
                start_date=start,
                end_date=end,
            ))
            aspects = list(self.nlp_store.aspect_results(
                model_id=DEFAULT_MODEL_ID,
                analyzer_version=ANALYZER_VERSION,
                company=company,
                start_date=start,
                end_date=end,
            ))
        except Exception as exc:  # UI detail panel must never break the base NLP view.
            self.nlp_log.append(f"NLP detay görünümü uyarısı: {exc}")
            return

        total = len(rows)
        high70 = sum(float(r["negative"]) >= 0.70 for r in rows)
        high90 = sum(float(r["negative"]) >= 0.90 for r in rows)
        low_conf = sum(float(r["confidence"]) < 0.60 for r in rows)
        summary = [
            ("Analiz edilen kayıt", str(total)),
            ("Ortalama model güveni", self._format_pct(self._mean(rows, "confidence"))),
            ("Ortalama negatif olasılık", self._format_pct(self._mean(rows, "negative"))),
            ("Ortalama nötr olasılık", self._format_pct(self._mean(rows, "neutral"))),
            ("Ortalama pozitif olasılık", self._format_pct(self._mean(rows, "positive"))),
            ("Yüksek negatiflik (≥ %70)", self._format_pct(high70 / total if total else None)),
            ("Çok yüksek negatiflik (≥ %90)", self._format_pct(high90 / total if total else None)),
            ("Düşük model güveni (< %60)", self._format_pct(low_conf / total if total else None)),
            ("Çözülenlerde ort. negatiflik", self._format_pct(self._mean(rows, "negative", lambda r: bool(r["resolved"])))),
            ("Çözülmeyenlerde ort. negatiflik", self._format_pct(self._mean(rows, "negative", lambda r: not bool(r["resolved"])))),
            ("Firma yanıtı olanlarda ort. negatiflik", self._format_pct(self._mean(rows, "negative", lambda r: bool(r["company_responded"])))),
            ("Firma yanıtı olmayanlarda ort. negatiflik", self._format_pct(self._mean(rows, "negative", lambda r: not bool(r["company_responded"])))),
        ]
        self.nlp_detail_summary.setRowCount(len(summary))
        for r, (label, value) in enumerate(summary):
            self.nlp_detail_summary.setItem(r, 0, QTableWidgetItem(label))
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignCenter)
            self.nlp_detail_summary.setItem(r, 1, value_item)

        self.nlp_aspect_detail_table.setRowCount(len(aspects))
        for r, row in enumerate(aspects):
            values = [
                row["category"],
                row["complaints"],
                row["sentences"],
                self._format_pct(row["mean_negative"]),
                self._format_pct(row["mean_neutral"]),
                self._format_pct(row["mean_positive"]),
                self._format_pct(row["unresolved_rate"]),
                self._duration(row["mean_response_hours"]),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.nlp_aspect_detail_table.setItem(r, c, item)

        uncertain = sorted(rows, key=lambda r: float(r["confidence"]))[:30]
        self.nlp_uncertain_table.setRowCount(len(uncertain))
        for r, row in enumerate(uncertain):
            values = [
                row["complaint_date"] or "",
                row["title"] or "",
                row["label"],
                f"%{float(row['confidence']) * 100:.1f}",
                f"%{float(row['negative']) * 100:.1f}",
                f"%{float(row['positive']) * 100:.1f}",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c == 1:
                    item.setToolTip(record_text(dict(row))[:3000])
                if c >= 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.nlp_uncertain_table.setItem(r, c, item)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = AdvancedMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
