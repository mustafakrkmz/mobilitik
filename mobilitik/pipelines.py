from __future__ import annotations

import sqlite3
from pathlib import Path

from mobilitik.config import DEFAULT_DB_PATH
from mobilitik.text_quality import normalize_space, sanitize_complaint_body


TIMING_COLUMNS = {
    "company_response_date": "TEXT",
    "response_hours": "REAL",
    "resolution_text": "TEXT",
    "resolution_date": "TEXT",
    "resolution_hours": "REAL",
}


class SQLitePipeline:
    def __init__(self, db_path: Path | str | None = None):
        self._custom_db_path = Path(db_path) if db_path is not None else None

    def open_spider(self, spider=None):
        if self._custom_db_path is not None:
            db_path = self._custom_db_path
        elif spider is not None and getattr(spider, "settings", None) and spider.settings.get("SQLITE_DB_PATH"):
            db_path = Path(spider.settings.get("SQLITE_DB_PATH"))
        elif Path.cwd().resolve() != DEFAULT_DB_PATH.parent.resolve():
            db_path = Path("mobilitik.db")
        else:
            db_path = DEFAULT_DB_PATH
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
            "CREATE INDEX IF NOT EXISTS idx_complaints_company_date ON complaints(company, complaint_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_complaints_resolved ON complaints(resolved)"
        )
        self._clean_existing_mixed_bodies()
        self.conn.commit()

    def _ensure_timing_columns(self):
        existing = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(complaints)").fetchall()
        }
        for column, sql_type in TIMING_COLUMNS.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE complaints ADD COLUMN {column} {sql_type}")

    def _clean_existing_mixed_bodies(self):
        """Repair legacy rows where SEO/company answers leaked into complaint_text."""
        rows = self.conn.execute(
            "SELECT id, complaint_text, company_response_text FROM complaints "
            "WHERE complaint_text IS NOT NULL"
        ).fetchall()
        for complaint_id, body, response in rows:
            cleaned = sanitize_complaint_body(body, response) or None
            original = normalize_space(body) or None
            if cleaned != original:
                self.conn.execute(
                    "UPDATE complaints SET complaint_text = ? WHERE id = ?",
                    (cleaned, complaint_id),
                )
                for table in ("sentiment_results", "aspect_sentiment"):
                    exists = self.conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,),
                    ).fetchone()
                    if exists:
                        self.conn.execute(
                            f"DELETE FROM {table} WHERE complaint_id = ?",
                            (complaint_id,),
                        )

    def process_item(self, item, spider=None):
        complaint_text = sanitize_complaint_body(
            item.get("complaint_text"),
            item.get("company_response_text"),
        ) or None
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
