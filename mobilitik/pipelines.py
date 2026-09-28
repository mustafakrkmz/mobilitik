from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLitePipeline:
    def open_spider(self, spider):
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
                listing_page INTEGER,
                scraped_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def process_item(self, item, spider):
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
                listing_page,
                scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(complaint_url) DO UPDATE SET
                complaint_date = excluded.complaint_date,
                title = excluded.title,
                complaint_text = excluded.complaint_text,
                resolved = excluded.resolved,
                company_responded = excluded.company_responded,
                company_response_text = excluded.company_response_text,
                listing_page = excluded.listing_page,
                scraped_at = excluded.scraped_at
            """,
            (
                item.get("company"),
                item.get("complaint_url"),
                item.get("complaint_date"),
                item.get("title"),
                item.get("complaint_text"),
                int(bool(item.get("resolved"))),
                int(bool(item.get("company_responded"))),
                item.get("company_response_text"),
                item.get("listing_page"),
                item.get("scraped_at"),
            ),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider):
        self.conn.close()
