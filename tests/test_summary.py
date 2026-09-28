from mobilitik.analysis.summary import category_summary


def test_category_summary_counts_multilabel_and_rates():
    rows = [
        {
            "title": "Teslimat gecikti ve montaj yapılmadı",
            "complaint_text": "Servis ekibi gelmedi.",
            "resolved": 1,
            "company_responded": 1,
        },
        {
            "title": "Teslimat gecikti",
            "complaint_text": "Kargo gelmedi.",
            "resolved": 0,
            "company_responded": 1,
        },
    ]

    summary = {row["category"]: row for row in category_summary(rows)}
    delivery = summary["Teslimat / Lojistik"]
    service = summary["Montaj / Servis"]

    assert delivery["complaints"] == 2
    assert delivery["resolved"] == 1
    assert delivery["resolved_rate"] == 50.0
    assert delivery["response_rate"] == 100.0
    assert service["complaints"] == 1
    assert service["resolved_rate"] == 100.0


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
