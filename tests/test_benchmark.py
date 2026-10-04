import sqlite3
from mobilitik.desktop.data import ComplaintRepository
from mobilitik.analysis.benchmark import compare_companies


def _seed_two_companies(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, response_hours, resolution_hours,
                scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("istikbal", "http://ex.test/1", "2026-03-01", "T1", "M1", 1, 1, 4.0, 24.0, "2026-03-01"),
                ("istikbal", "http://ex.test/2", "2026-03-02", "T2", "M2", 0, 1, 8.0, None, "2026-03-02"),
                ("bellona", "http://ex.test/3", "2026-03-01", "T3", "M3", 1, 1, 2.0, 12.0, "2026-03-01"),
            ],
        )


def test_compare_companies_calculates_rates_and_deltas(tmp_path):
    db_path = tmp_path / "test.db"
    repo = ComplaintRepository(db_path)
    _seed_two_companies(db_path)

    result = compare_companies(repo, "istikbal", "bellona")
    assert result["company1"]["name"] == "istikbal"
    assert result["company1"]["metrics"]["total"] == 2
    assert result["company1"]["resolution_rate"] == 50.0
    assert result["company1"]["response_rate"] == 100.0

    assert result["company2"]["name"] == "bellona"
    assert result["company2"]["metrics"]["total"] == 1
    assert result["company2"]["resolution_rate"] == 100.0

    assert len(result["rows"]) == 5
