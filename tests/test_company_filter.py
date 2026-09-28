import sqlite3

from mobilitik.desktop.data import ComplaintRepository


def test_repository_filter_accepts_company_root_url(tmp_path):
    db_path = tmp_path / "company-filter.db"
    repo = ComplaintRepository(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO complaints (
                company, complaint_url, complaint_date, title, complaint_text,
                resolved, company_responded, listing_page, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cilek-mobilya",
                "https://www.sikayetvar.com/cilek-mobilya/ornek-sikayet",
                "2026-09-20 12:00:00",
                "Örnek şikâyet",
                "Teslimat gecikiyor.",
                0,
                0,
                1,
                "2026-09-20T13:00:00",
            ),
        )

    rows = repo.filtered_complaints(
        company="https://www.sikayetvar.com/cilek-mobilya",
        start_date="2026-09-01",
        end_date="2026-09-30",
    )
    assert len(rows) == 1
    assert rows[0]["company"] == "cilek-mobilya"
