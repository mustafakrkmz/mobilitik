from __future__ import annotations

import html
import re
from typing import Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mobilitik.analysis.classifier import classify_record


def record_text(record: dict) -> str:
    """Return the best available complaint text without inventing content."""
    complaint = (record.get("complaint_text") or "").strip()
    if complaint:
        return complaint
    title = (record.get("title") or "").strip()
    if title:
        return title
    return "Bu kayıtta gösterilebilecek bir şikâyet metni veya başlık yok."


def highlight_html(text: str, terms: Iterable[str] | str | None) -> str:
    """Escapes HTML and highlights specified terms in bold red."""
    escaped = html.escape(text or "")
    if not terms:
        return escaped.replace("\n", "<br>")

    if isinstance(terms, str):
        term_list = [terms]
    else:
        term_list = [str(t) for t in terms if t and str(t).strip()]

    term_list = sorted({t.strip() for t in term_list if t.strip()}, key=len, reverse=True)
    if not term_list:
        return escaped.replace("\n", "<br>")

    pattern = "|".join(re.escape(html.escape(t)) for t in term_list)
    highlighted = re.sub(
        rf"(?i)({pattern})",
        r'<b style="color: #ef4444; font-weight: bold; background-color: rgba(239, 68, 68, 0.15); padding: 1px 3px; border-radius: 3px;">\1</b>',
        escaped,
    )
    return highlighted.replace("\n", "<br>")


class ComplaintDrilldownDialog(QDialog):
    """Zenginleştirilmiş şikâyet listesi ve terim vurgulama diyaloğu."""

    def __init__(
        self,
        title: str,
        records: list[dict],
        parent=None,
        *,
        highlight_terms: Iterable[str] | str | None = None,
        explanations: dict[int, str] | None = None,
    ):
        super().__init__(parent)
        self.records = list(records)
        self.highlight_terms = highlight_terms
        self.explanations = explanations or {}
        self.setWindowTitle(title)
        self.resize(960, 720)

        outer = QVBoxLayout(self)
        summary = QLabel(f"{len(self.records)} şikâyet listeleniyor.")
        summary.setStyleSheet("font-weight: 600; font-size: 11pt;")
        outer.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cards = QVBoxLayout(container)
        cards.setSpacing(12)

        for index, record in enumerate(self.records, start=1):
            date = record.get("complaint_date") or "Tarih yok"
            complaint_title = record.get("title") or "Başlıksız şikâyet"
            text = record_text(record)
            url = record.get("complaint_url") or ""
            rec_id = record.get("id")

            box = QGroupBox(f"{index}. {complaint_title}")
            box_layout = QVBoxLayout(box)
            meta = QHBoxLayout()
            date_label = QLabel(f"<b>Zaman:</b> {html.escape(str(date))}")
            meta.addWidget(date_label)

            # Çözülme / Yanıt durumu etiketleri
            if record.get("resolved"):
                res_badge = QLabel("✓ Çözüldü")
                res_badge.setStyleSheet("color: #10b981; font-weight: bold; margin-left: 8px;")
                meta.addWidget(res_badge)
            if record.get("company_responded"):
                resp_badge = QLabel("💬 Firma Yanıtı Var")
                resp_badge.setStyleSheet("color: #38bdf8; font-weight: bold; margin-left: 8px;")
                meta.addWidget(resp_badge)

            meta.addStretch()
            if url:
                safe_url = html.escape(url, quote=True)
                link = QLabel(f'<a href="{safe_url}">Kaynağı aç ↗</a>')
                link.setOpenExternalLinks(True)
                link.setTextInteractionFlags(Qt.TextBrowserInteraction)
                meta.addWidget(link)
            box_layout.addLayout(meta)

            # Atama gerekçesi / Eşleşen terimler açıklaması
            explanation = self.explanations.get(rec_id) or self.explanations.get(index)
            if explanation:
                exp_label = QLabel(
                    f'<div style="background: rgba(56, 189, 248, 0.12); color: #7dd3fc; border: 1px solid #0284c7; padding: 5px 8px; border-radius: 6px; font-size: 9pt;">'
                    f'ℹ️ <b>Kategoriye Atama Nedeni:</b> {html.escape(explanation)}</div>'
                )
                exp_label.setWordWrap(True)
                box_layout.addWidget(exp_label)

            heading_html = highlight_html(f"Başlık: {complaint_title}", self.highlight_terms)
            heading = QLabel(heading_html)
            heading.setWordWrap(True)
            box_layout.addWidget(heading)

            body_html = highlight_html(text, self.highlight_terms)
            body = QLabel(body_html)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setStyleSheet("padding: 6px 2px; line-height: 140%;")
            box_layout.addWidget(body)
            cards.addWidget(box)

        cards.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)


class ComplaintDetailDialog(QDialog):
    """Tek bir şikâyetin tüm detaylarını gösteren modal pencere."""

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = dict(record)
        title = self.record.get("title") or "Başlıksız Şikâyet"
        self.setWindowTitle(f"Şikâyet Detayı — {title}")
        self.resize(880, 680)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Üst Başlık ve Meta Bilgiler
        header_group = QGroupBox("Genel Bilgiler")
        hg_layout = QGridLayout(header_group)
        hg_layout.addWidget(QLabel("<b>Firma:</b>"), 0, 0)
        hg_layout.addWidget(QLabel(str(self.record.get("company") or "—").upper()), 0, 1)
        hg_layout.addWidget(QLabel("<b>Tarih:</b>"), 0, 2)
        hg_layout.addWidget(QLabel(str(self.record.get("complaint_date") or "—")), 0, 3)

        resolved_text = "✓ Çözüldü" if self.record.get("resolved") else "✗ Çözülmedi"
        resolved_color = "#10b981" if self.record.get("resolved") else "#ef4444"
        hg_layout.addWidget(QLabel("<b>Durum:</b>"), 1, 0)
        r_label = QLabel(resolved_text)
        r_label.setStyleSheet(f"color: {resolved_color}; font-weight: bold;")
        hg_layout.addWidget(r_label, 1, 1)

        responded_text = "✓ Yanıtlandı" if self.record.get("company_responded") else "✗ Yanıtsız"
        hg_layout.addWidget(QLabel("<b>Firma Yanıtı:</b>"), 1, 2)
        hg_layout.addWidget(QLabel(responded_text), 1, 3)

        # Otomatik Kategori Sınıflandırması
        classification = classify_record(self.record.get("title"), self.record.get("complaint_text"))
        cats = classification.categories or ["Diğer"]
        cat_details = []
        for cat in cats:
            hits = classification.matched_terms.get(cat, [])
            if hits:
                cat_details.append(f"{cat} ({', '.join(hits)})")
            else:
                cat_details.append(cat)
        hg_layout.addWidget(QLabel("<b>Kategoriler:</b>"), 2, 0)
        cat_label = QLabel("; ".join(cat_details))
        cat_label.setStyleSheet("color: #38bdf8;")
        hg_layout.addWidget(cat_label, 2, 1, 1, 3)

        url = self.record.get("complaint_url") or ""
        if url:
            safe_url = html.escape(url, quote=True)
            link = QLabel(f'<a href="{safe_url}">Şikayetvar Sayfasını Tarayıcıda Aç ↗</a>')
            link.setOpenExternalLinks(True)
            link.setTextInteractionFlags(Qt.TextBrowserInteraction)
            hg_layout.addWidget(link, 3, 0, 1, 4)

        layout.addWidget(header_group)

        # Şikâyet Başlığı ve Metni
        complaint_group = QGroupBox("Tüketici Şikâyeti")
        cg_layout = QVBoxLayout(complaint_group)
        title_lbl = QLabel(f"<h3>{html.escape(title)}</h3>")
        title_lbl.setWordWrap(True)
        cg_layout.addWidget(title_lbl)

        body_edit = QTextEdit()
        body_edit.setReadOnly(True)
        body_edit.setPlainText(record_text(self.record))
        cg_layout.addWidget(body_edit)
        layout.addWidget(complaint_group, 2)

        # Firma Yanıtı ve Çözüm Detayları
        if self.record.get("company_response_text") or self.record.get("company_response_date"):
            resp_group = QGroupBox("Firma Yanıtı Detayı")
            rg_layout = QVBoxLayout(resp_group)
            meta_resp = f"Tarih: {self.record.get('company_response_date') or '—'}"
            if self.record.get("response_hours") is not None:
                meta_resp += f" (Süre: {self.record.get('response_hours'):.1f} saat)"
            rg_layout.addWidget(QLabel(meta_resp))
            if self.record.get("company_response_text"):
                resp_text = QTextEdit()
                resp_text.setReadOnly(True)
                resp_text.setMaximumHeight(90)
                resp_text.setPlainText(self.record["company_response_text"])
                rg_layout.addWidget(resp_text)
            layout.addWidget(resp_group)

        if self.record.get("resolution_text") or self.record.get("resolution_date"):
            sol_group = QGroupBox("Çözüm Bilgisi")
            sg_layout = QVBoxLayout(sol_group)
            meta_sol = f"Tarih: {self.record.get('resolution_date') or '—'}"
            if self.record.get("resolution_hours") is not None:
                meta_sol += f" (Süre: {self.record.get('resolution_hours'):.1f} saat)"
            sg_layout.addWidget(QLabel(meta_sol))
            if self.record.get("resolution_text"):
                sol_text = QTextEdit()
                sol_text.setReadOnly(True)
                sol_text.setMaximumHeight(90)
                sol_text.setPlainText(self.record["resolution_text"])
                sg_layout.addWidget(sol_text)
            layout.addWidget(sol_group)

        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)


class SentimentExplanationDialog(QDialog):
    """Duygu analizi atamasının nedenlerini ve cümle bazlı dağılımını gösteren açıklanabilirlik penceresi."""

    def __init__(self, record: dict, sentiment_score: dict | None = None, parent=None):
        super().__init__(parent)
        self.record = dict(record)
        self.sentiment = sentiment_score or {}
        title = self.record.get("title") or "Başlıksız Şikâyet"
        self.setWindowTitle(f"Duygu Analizi Açıklaması — {title}")
        self.resize(920, 700)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Genel Skorlar Kartı
        score_group = QGroupBox("Genel Duygu Skoru ve Olasılıklar")
        sg_layout = QGridLayout(score_group)

        lbl = str(self.sentiment.get("label") or "—")
        conf = float(self.sentiment.get("confidence") or 0.0) * 100
        neg = float(self.sentiment.get("negative") or 0.0) * 100
        neu = float(self.sentiment.get("neutral") or 0.0) * 100
        pos = float(self.sentiment.get("positive") or 0.0) * 100

        color_map = {
            "Negatif": "#ef4444",
            "Nötr": "#94a3b8",
            "Pozitif": "#10b981",
            "negative": "#ef4444",
            "neutral": "#94a3b8",
            "positive": "#10b981",
        }
        badge = QLabel(
            f"<span style='font-size: 15pt; font-weight: bold; color: {color_map.get(lbl, '#38bdf8')};'>{lbl.upper()}</span> "
            f"(Model Güveni: %{conf:.1f})"
        )
        sg_layout.addWidget(badge, 0, 0, 1, 3)

        sg_layout.addWidget(QLabel(f"<b>🔴 Negatif:</b> %{neg:.1f}"), 1, 0)
        sg_layout.addWidget(QLabel(f"<b>⚪ Nötr:</b> %{neu:.1f}"), 1, 1)
        sg_layout.addWidget(QLabel(f"<b>🟢 Pozitif:</b> %{pos:.1f}"), 1, 2)
        layout.addWidget(score_group)

        # Şikâyet Tam Metni
        text_group = QGroupBox("İncelenen Şikâyet Metni")
        tg_layout = QVBoxLayout(text_group)
        t_edit = QTextEdit()
        t_edit.setReadOnly(True)
        t_edit.setPlainText(record_text(self.record))
        t_edit.setMaximumHeight(130)
        tg_layout.addWidget(t_edit)
        layout.addWidget(text_group)

        # Cümle ve Aspect Açıklamaları
        aspect_group = QGroupBox("Cümle ve Boyut (Aspect) Açıklaması")
        ag_layout = QVBoxLayout(aspect_group)
        info_lbl = QLabel(
            "Şikâyet cümlelere ayrılmış ve Mobilitik kategori kurallarıyla eşleştirilmiştir. "
            "Her cümlenin tetiklediği kategori ve anahtar kelimeler aşağıdadır:"
        )
        info_lbl.setStyleSheet("color: #94a3b8;")
        ag_layout.addWidget(info_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        sc_widget = QWidget()
        sc_layout = QVBoxLayout(sc_widget)
        sc_layout.setSpacing(8)

        from mobilitik.analysis.sentiment import split_sentences
        sentences = split_sentences(record_text(self.record))
        for idx, sentence in enumerate(sentences, start=1):
            s_class = classify_record(sentence, None)
            cats = s_class.categories or ["Genel"]
            matched_terms = [
                f"{c}: {', '.join(terms)}"
                for c, terms in s_class.matched_terms.items()
                if terms
            ]

            card = QFrame()
            card.setObjectName("dashboardCard")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 8, 10, 8)
            cat_text = f"<b>{idx}. Kategori:</b> {', '.join(cats)}"
            if matched_terms:
                cat_text += f" <span style='color: #7dd3fc;'>({'; '.join(matched_terms)})</span>"
            c_layout.addWidget(QLabel(cat_text))

            sent_lbl = QLabel(f'<span style="line-height: 130%;">{html.escape(sentence)}</span>')
            sent_lbl.setWordWrap(True)
            c_layout.addWidget(sent_lbl)
            sc_layout.addWidget(card)

        sc_layout.addStretch()
        scroll.setWidget(sc_widget)
        ag_layout.addWidget(scroll)
        layout.addWidget(aspect_group, 2)

        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)
