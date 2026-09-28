from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def record_text(record: dict) -> str:
    """Return the best available complaint text without inventing content."""
    complaint = (record.get("complaint_text") or "").strip()
    if complaint:
        return complaint
    title = (record.get("title") or "").strip()
    if title:
        return title
    return "Bu kayıtta gösterilebilecek bir şikâyet metni veya başlık yok."


class ComplaintDrilldownDialog(QDialog):
    """Simple, readable list of complaints for word/category drill-downs."""

    def __init__(self, title: str, records: list[dict], parent=None):
        super().__init__(parent)
        self.records = list(records)
        self.setWindowTitle(title)
        self.resize(920, 680)

        outer = QVBoxLayout(self)
        summary = QLabel(f"{len(self.records)} şikâyet gösteriliyor.")
        summary.setStyleSheet("font-weight: 600;")
        outer.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cards = QVBoxLayout(container)
        cards.setSpacing(10)

        for index, record in enumerate(self.records, start=1):
            date = record.get("complaint_date") or "Tarih yok"
            complaint_title = record.get("title") or "Başlıksız şikâyet"
            text = record_text(record)
            url = record.get("complaint_url") or ""

            box = QGroupBox(f"{index}. {complaint_title}")
            box_layout = QVBoxLayout(box)
            meta = QHBoxLayout()
            date_label = QLabel(f"<b>Zaman:</b> {html.escape(str(date))}")
            meta.addWidget(date_label)
            meta.addStretch()
            if url:
                safe_url = html.escape(url, quote=True)
                link = QLabel(f'<a href="{safe_url}">Kaynağı aç ↗</a>')
                link.setOpenExternalLinks(True)
                link.setTextInteractionFlags(Qt.TextBrowserInteraction)
                meta.addWidget(link)
            box_layout.addLayout(meta)

            heading = QLabel(f"<b>Başlık:</b> {html.escape(str(complaint_title))}")
            heading.setWordWrap(True)
            box_layout.addWidget(heading)

            body = QLabel(html.escape(text).replace("\n", "<br>"))
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setStyleSheet("padding: 6px 2px;")
            box_layout.addWidget(body)
            cards.addWidget(box)

        cards.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)
