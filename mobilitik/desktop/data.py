from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from mobilitik.company import normalize_company_input
from mobilitik.timing import median


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
    "company_response_date",
    "response_hours",
    "resolution_text",
    "resolution_date",
    "resolution_hours",
    "listing_page",
    "scraped_at",
]

TIMING_COLUMNS = {
    "company_response_date": "TEXT",
    "response_hours": "REAL",
    "resolution_text": "TEXT",
    "resolution_date": "TEXT",
    "resolution_hours": "REAL",
}

# Historic Mobilitik versions accidentally accepted Sikayetvar's SEO/link-preview
# sentence as complaint_text. These patterns identify that copy, not user content.
_BOILERPLATE_SQL = """
    complaint_text IS NOT NULL AND (
        complaint_text LIKE '%şikayetini ve yorumlarını okumak%'
        OR complaint_text LIKE '%şikâyetini ve yorumlarını okumak%'
        OR complaint_text LIKE '%hakkında şikayet yazmak için tıklayın%'
        OR complaint_text LIKE '%hakkında şikâyet yazmak için tıklayın%'
        OR complaint_text LIKE '%Visit to read complaints and reviews%'
    )
"""


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
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(complaints)").fetchall()
            }
            for column, sql_type in TIMING_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE complaints ADD COLUMN {column} {sql_type}")

            # Data-quality migration: never feed legacy SEO preview copy into
            # word/category/verb/NLP analyses. Re-scraping the same complaint URL
            # will refill the body with the real text or listing excerpt.
            conn.execute(f"UPDATE complaints SET complaint_text = NULL WHERE {_BOILERPLATE_SQL}")

    @staticmethod
    def _metrics_from_rows(rows):
        rows = list(rows)
        total = len(rows)
        return {
            "total": total,
            "resolved": sum(int(bool(row["resolved"])) for row in rows),
            "responded": sum(int(bool(row["company_responded"])) for row in rows),
            "timed_responses": sum(row["response_hours"] is not None for row in rows),
            "timed_resolutions": sum(row["resolution_hours"] is not None for row in rows),
            "median_response_hours": median(row["response_hours"] for row in rows),
            "median_resolution_hours": median(row["resolution_hours"] for row in rows),
        }

    def metrics(self):
        return self._metrics_from_rows(self.all_complaints())

    def filtered_metrics(self, company: str | None = None, start_date: str | None = None, end_date: str | None = None):
        return self._metrics_from_rows(
            self.filtered_complaints(company=company, start_date=start_date, end_date=end_date)
        )

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
            params.append(normalize_company_input(company))
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
