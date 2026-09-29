from __future__ import annotations

import sqlite3
from pathlib import Path

from mobilitik.text_quality import sanitize_complaint_body


TIMING_COLUMNS = {
    "company_response_date": "TEXT",
    "response_hours": "REAL",
    "resolution_text": "TEXT",
    "resolution_date": "TEXT",
    "resolution_hours": "REAL",
}


class SQLitePipeline:
    def open_spider(self, spider=None):
        db_path = Path("mobilitik.db")
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                complaint_url TEXT NOT NULL UNIQUE,
                complaint_date TEXT,
                title TEXT,
                complaint_text TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                company_responded INTEGER NOT NULL DEFAULT 0,
                company_response_text TEXT,
                company_response_date TEXT,
                response_hours REAL,
                resolution_text TEXT,
                resolution_date TEXT,
                resolution_hours REAL,
                listing_page INTEGER,
                scraped_at TEXT NOT NULL
            )
            """
        )
        self._ensure_timing_columns()
        self.conn.execute(
            """
            UPDATE complaints SET complaint_text = NULL
            WHERE complaint_text IS NOT NULL AND (
                complaint_text LIKE '%şikayetini ve yorumlarını okumak%'
                OR complaint_text LIKE '%şikâyetini ve yorumlarını okumak%'
                OR complaint_text LIKE '%hakkında şikayet yazmak için tıklayın%'
                OR complaint_text LIKE '%hakkında şikâyet yazmak için tıklayın%'
                OR complaint_text LIKE '%Visit to read complaints and reviews%'
            )
            """
        )
        self.conn.commit()

    def _ensure_timing_columns(self):
        existing = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(complaints)").fetchall()
        }
        for column, sql_type in TIMING_COLUMNS.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE complaints ADD COLUMN {column} {sql_type}")

    def process_item(self, item, spider=None):
        complaint_text = sanitize_complaint_body(item.get("complaint_text")) or None
        self.conn.execute(
            """
            INSERT INTO complaints (
                company,
                complaint_url,
                complaint_date,
                title,
                complaint_text,
                resolved,
                company_responded,
                company_response_text,
                company_response_date,
                response_hours,
                resolution_text,
                resolution_date,
                resolution_hours,
                listing_page,
                scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(complaint_url) DO UPDATE SET
                complaint_date = excluded.complaint_date,
                title = excluded.title,
                complaint_text = COALESCE(excluded.complaint_text, complaints.complaint_text),
                resolved = excluded.resolved,
                company_responded = excluded.company_responded,
                company_response_text = excluded.company_response_text,
                company_response_date = excluded.company_response_date,
                response_hours = excluded.response_hours,
                resolution_text = excluded.resolution_text,
                resolution_date = excluded.resolution_date,
                resolution_hours = excluded.resolution_hours,
                listing_page = excluded.listing_page,
                scraped_at = excluded.scraped_at
            """,
            (
                item.get("company"),
                item.get("complaint_url"),
                item.get("complaint_date"),
                item.get("title"),
                complaint_text,
                int(bool(item.get("resolved"))),
                int(bool(item.get("company_responded"))),
                item.get("company_response_text"),
                item.get("company_response_date"),
                item.get("response_hours"),
                item.get("resolution_text"),
                item.get("resolution_date"),
                item.get("resolution_hours"),
                item.get("listing_page"),
                item.get("scraped_at"),
            ),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider=None):
        self.conn.close()
