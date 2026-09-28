from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Iterable


class SentimentStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentiment_results (
                    complaint_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    analyzer_version TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    label TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    negative REAL NOT NULL,
                    neutral REAL NOT NULL,
                    positive REAL NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    PRIMARY KEY (complaint_id, model_id, analyzer_version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS aspect_sentiment (
                    complaint_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    analyzer_version TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    sentence_count INTEGER NOT NULL,
                    negative REAL NOT NULL,
                    neutral REAL NOT NULL,
                    positive REAL NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    PRIMARY KEY (complaint_id, category, model_id, analyzer_version)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sentiment_model ON sentiment_results(model_id, analyzer_version)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_aspect_model_category ON aspect_sentiment(model_id, analyzer_version, category)"
            )

    def cached_hash(self, complaint_id: int, model_id: str, analyzer_version: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT text_hash FROM sentiment_results
                WHERE complaint_id = ? AND model_id = ? AND analyzer_version = ?
                """,
                (complaint_id, model_id, analyzer_version),
            ).fetchone()
        return row["text_hash"] if row else None

    def aspect_cached_hash(self, complaint_id: int, model_id: str, analyzer_version: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT text_hash FROM aspect_sentiment
                WHERE complaint_id = ? AND model_id = ? AND analyzer_version = ?
                LIMIT 1
                """,
                (complaint_id, model_id, analyzer_version),
            ).fetchone()
        return row["text_hash"] if row else None

    def upsert_sentiment(
        self,
        complaint_id: int,
        model_id: str,
        analyzer_version: str,
        text_hash: str,
        *,
        label: str,
        confidence: float,
        negative: float,
        neutral: float,
        positive: float,
    ):
        analyzed_at = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sentiment_results (
                    complaint_id, model_id, analyzer_version, text_hash,
                    label, confidence, negative, neutral, positive, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(complaint_id, model_id, analyzer_version) DO UPDATE SET
                    text_hash = excluded.text_hash,
                    label = excluded.label,
                    confidence = excluded.confidence,
                    negative = excluded.negative,
                    neutral = excluded.neutral,
                    positive = excluded.positive,
                    analyzed_at = excluded.analyzed_at
                """,
                (
                    complaint_id,
                    model_id,
                    analyzer_version,
                    text_hash,
                    label,
                    confidence,
                    negative,
                    neutral,
                    positive,
                    analyzed_at,
                ),
            )

    def replace_aspects(
        self,
        complaint_id: int,
        model_id: str,
        analyzer_version: str,
        text_hash: str,
        aspects: Iterable[dict],
    ):
        analyzed_at = dt.datetime.now().isoformat(timespec="seconds")
        rows = list(aspects)
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM aspect_sentiment
                WHERE complaint_id = ? AND model_id = ? AND analyzer_version = ?
                """,
                (complaint_id, model_id, analyzer_version),
            )
            conn.executemany(
                """
                INSERT INTO aspect_sentiment (
                    complaint_id, category, model_id, analyzer_version, text_hash,
                    sentence_count, negative, neutral, positive, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        complaint_id,
                        row["category"],
                        model_id,
                        analyzer_version,
                        text_hash,
                        int(row["sentence_count"]),
                        float(row["negative"]),
                        float(row["neutral"]),
                        float(row["positive"]),
                        analyzed_at,
                    )
                    for row in rows
                ],
            )

    @staticmethod
    def _filter_sql(company: str | None, start_date: str | None, end_date: str | None):
        clauses: list[str] = []
        params: list[str] = []
        if company:
            clauses.append("c.company = ?")
            params.append(company)
        if start_date:
            clauses.append("date(c.complaint_date) >= date(?)")
            params.append(start_date)
        if end_date:
            clauses.append("date(c.complaint_date) <= date(?)")
            params.append(end_date)
        return (" AND " + " AND ".join(clauses)) if clauses else "", params

    def complaint_results(
        self,
        *,
        model_id: str,
        analyzer_version: str,
        company: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        filters, params = self._filter_sql(company, start_date, end_date)
        with self._connect() as conn:
            return conn.execute(
                f"""
                SELECT
                    c.id, c.company, c.complaint_date, c.title, c.complaint_text,
                    c.resolved, c.company_responded, c.response_hours, c.resolution_hours,
                    s.label, s.confidence, s.negative, s.neutral, s.positive,
                    s.analyzed_at
                FROM complaints c
                JOIN sentiment_results s ON s.complaint_id = c.id
                WHERE s.model_id = ? AND s.analyzer_version = ? {filters}
                ORDER BY COALESCE(c.complaint_date, c.scraped_at) DESC, c.id DESC
                """,
                [model_id, analyzer_version, *params],
            ).fetchall()

    def aspect_results(
        self,
        *,
        model_id: str,
        analyzer_version: str,
        company: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        filters, params = self._filter_sql(company, start_date, end_date)
        with self._connect() as conn:
            return conn.execute(
                f"""
                SELECT
                    a.category,
                    COUNT(*) AS complaints,
                    SUM(a.sentence_count) AS sentences,
                    AVG(a.negative) AS mean_negative,
                    AVG(a.neutral) AS mean_neutral,
                    AVG(a.positive) AS mean_positive,
                    AVG(CASE WHEN a.negative >= 0.70 THEN 1.0 ELSE 0.0 END) AS high_negative_rate,
                    AVG(CASE WHEN c.resolved THEN 0.0 ELSE 1.0 END) AS unresolved_rate,
                    AVG(c.response_hours) AS mean_response_hours
                FROM aspect_sentiment a
                JOIN complaints c ON c.id = a.complaint_id
                WHERE a.model_id = ? AND a.analyzer_version = ? {filters}
                GROUP BY a.category
                ORDER BY complaints DESC, a.category
                """,
                [model_id, analyzer_version, *params],
            ).fetchall()

    def counts(
        self,
        *,
        model_id: str,
        analyzer_version: str,
        company: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, float | int]:
        rows = list(
            self.complaint_results(
                model_id=model_id,
                analyzer_version=analyzer_version,
                company=company,
                start_date=start_date,
                end_date=end_date,
            )
        )
        total = len(rows)
        if not total:
            return {
                "total": 0,
                "negative": 0,
                "neutral": 0,
                "positive": 0,
                "mean_negative": 0.0,
            }
        return {
            "total": total,
            "negative": sum(row["label"] == "negative" for row in rows),
            "neutral": sum(row["label"] == "neutral" for row in rows),
            "positive": sum(row["label"] == "positive" for row in rows),
            "mean_negative": sum(float(row["negative"]) for row in rows) / total,
        }
