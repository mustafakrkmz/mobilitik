from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


COLUMNS = [
    "id",
    "company",
    "complaint_url",
    "complaint_date",
    "title",
    "complaint_text",
    "resolved",
    "company_responded",
    "company_response_text",
    "listing_page",
    "scraped_at",
]


class ComplaintRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._ensure_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self):
        with self._connect() as conn:
            conn.execute(
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

    def metrics(self):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(resolved), 0) AS resolved,
                    COALESCE(SUM(company_responded), 0) AS responded
                FROM complaints
                """
            ).fetchone()
        return dict(row)

    def list_complaints(self, limit: int = 500):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM complaints
                ORDER BY COALESCE(complaint_date, scraped_at) DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return rows

    def filtered_complaints(self, company: str | None = None, start_date: str | None = None, end_date: str | None = None):
        clauses = []
        params: list[str] = []

        if company:
            clauses.append("company = ?")
            params.append(company)
        if start_date:
            clauses.append("date(complaint_date) >= date(?)")
            params.append(start_date)
        if end_date:
            clauses.append("date(complaint_date) <= date(?)")
            params.append(end_date)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT *
            FROM complaints
            {where}
            ORDER BY COALESCE(complaint_date, scraped_at) DESC, id DESC
        """
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def all_complaints(self):
        return self.filtered_complaints()

    def export_csv(self, path: Path):
        rows = self.all_complaints()
        with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row[column] for column in COLUMNS})

    def export_xlsx(self, path: Path):
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise RuntimeError("Excel dışa aktarımı için openpyxl kurulmalıdır.") from exc

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Şikâyetler"
        sheet.append(COLUMNS)

        for row in self.all_complaints():
            sheet.append([row[column] for column in COLUMNS])

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(path)
