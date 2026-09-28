from mobilitik.analysis.summary import category_summary


def test_category_summary_counts_multilabel_rates_and_timing():
    rows = [
        {
            "title": "Teslimat gecikti ve montaj yapılmadı",
            "complaint_text": "Servis ekibi gelmedi.",
            "resolved": 1,
            "company_responded": 1,
            "response_hours": 4.0,
            "resolution_hours": 48.0,
        },
        {
            "title": "Teslimat gecikti",
            "complaint_text": "Kargo gelmedi.",
            "resolved": 0,
            "company_responded": 1,
            "response_hours": 8.0,
            "resolution_hours": None,
        },
    ]

    summary = {row["category"]: row for row in category_summary(rows)}
    delivery = summary["Teslimat / Lojistik"]
    service = summary["Montaj / Servis"]

    assert delivery["complaints"] == 2
    assert delivery["resolved"] == 1
    assert delivery["resolved_rate"] == 50.0
    assert delivery["response_rate"] == 100.0
    assert delivery["median_response_hours"] == 6.0
    assert delivery["median_resolution_hours"] == 48.0
    assert delivery["timed_responses"] == 2
    assert delivery["timed_resolutions"] == 1
    assert service["complaints"] == 1
    assert service["resolved_rate"] == 100.0
    assert service["median_response_hours"] == 4.0


def test_category_summary_puts_unmatched_in_other():
    summary = category_summary([
        {
            "title": "Genel memnuniyetsizlik",
            "complaint_text": "Beklediğim gibi değildi.",
            "resolved": 0,
            "company_responded": 0,
        }
    ])
    assert summary[0]["category"] == "Diğer"
    assert summary[0]["complaints"] == 1
    assert summary[0]["median_response_hours"] is None
    assert summary[0]["median_resolution_hours"] is None
