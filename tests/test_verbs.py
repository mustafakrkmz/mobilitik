from mobilitik.analysis.verbs import extract_progressive_verb, progressive_verb_stats


def test_extract_progressive_verb_stems_requested_suffixes():
    assert extract_progressive_verb("geliyor") == "gel"
    assert extract_progressive_verb("gidiyor") == "gid"
    assert extract_progressive_verb("çalışıyor") == "çalış"
    assert extract_progressive_verb("bozuluyor") == "bozul"
    assert extract_progressive_verb("dönüşüyor") == "dönüş"
    assert extract_progressive_verb("geldi") is None


def test_progressive_verb_stats_counts_frequency_documents_and_examples():
    rows = progressive_verb_stats([
        "Servis gelmiyor, firma cevap vermiyor.",
        "Ürün sürekli bozuluyor ve servis yine gelmiyor.",
        "Firma bugün arıyor ama sorun devam ediyor.",
    ])
    by_stem = {row.stem: row for row in rows}
    assert by_stem["gelm"].count == 2
    assert by_stem["gelm"].document_count == 2
    assert "gelmiyor" in by_stem["gelm"].examples
    assert by_stem["bozul"].count == 1
    assert by_stem["arıyor"[:-4] if False else "ar"].count == 1
