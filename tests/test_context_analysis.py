from mobilitik.analysis.context import analyze_context


def _records():
    return [
        {
            "title": "Verona koltuk takımı sorunu",
            "complaint_text": "Verona koltuk takımı kumaşı kısa sürede açıldı.",
            "company_response_text": None,
        },
        {
            "title": "Mavenna koltuk takımı gecikmesi",
            "complaint_text": "Mavenna koltuk takımı teslimatı gecikti.",
            "company_response_text": None,
        },
        {
            "title": "Verona koltuk takımı tekrar sorun çıkardı",
            "complaint_text": "Verona koltuk takımı için servis bekliyorum.",
            "company_response_text": None,
        },
        {
            "title": "Düzce bayisinden teslimat sorunu",
            "complaint_text": "Düzce bayisinden aldığım ürün geç geldi.",
            "company_response_text": None,
        },
        {
            "title": "Ankara Siteler bayisinden ürün aldım",
            "complaint_text": "Ankara Siteler bayisinden teslimat yapılmadı.",
            "company_response_text": None,
        },
    ]


def test_left_context_finds_product_names():
    hits, mapping, meta = analyze_context(_records(), "koltuk takımı", direction="left", window=1)
    by_context = {hit.context: hit for hit in hits}
    assert by_context["verona"].document_count == 2
    assert by_context["mavenna"].document_count == 1
    assert by_context["verona"].count >= 2
    assert meta["anchor_documents"] == 3
    assert len(mapping["verona"]) == 2


def test_prefix_anchor_matches_inflected_bayi_forms():
    hits, _mapping, meta = analyze_context(_records(), "bayi*", direction="left", window=2)
    contexts = {hit.context for hit in hits}
    assert any("düzce" in context for context in contexts)
    assert any("ankara siteler" in context for context in contexts)
    assert meta["anchor_documents"] == 2


def test_company_response_is_not_used_as_context():
    records = [{
        "title": "Teslimat sorunu",
        "complaint_text": "Teslimat gecikti. Değerli Müşterimiz, öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz.",
        "company_response_text": "Değerli Müşterimiz, öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz.",
    }]
    hits, _mapping, _meta = analyze_context(records, "teslimat", direction="right", window=1)
    assert hits
    assert hits[0].context == "sorunu" or hits[0].context == "gecikti"
    assert all("değerli" not in hit.context for hit in hits)
