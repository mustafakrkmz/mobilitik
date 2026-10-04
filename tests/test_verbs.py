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
    assert by_stem["ar"].count == 1


def test_registered_root_matching_and_sentence_listing():
    from mobilitik.analysis.verbs import (
        DEFAULT_REGISTERED_ROOTS,
        extract_registered_root_expressions,
        find_sentences_with_registered_roots,
        match_registered_root,
    )

    # Test inflection matching against registered roots
    assert match_registered_root("geliyor", DEFAULT_REGISTERED_ROOTS) == "gel"
    assert match_registered_root("gelmedi", DEFAULT_REGISTERED_ROOTS) == "gel"
    assert match_registered_root("gidiyor", DEFAULT_REGISTERED_ROOTS) == "git"
    assert match_registered_root("gitti", DEFAULT_REGISTERED_ROOTS) == "git"
    assert match_registered_root("yapıldı", DEFAULT_REGISTERED_ROOTS) == "yap"
    assert match_registered_root("yapılmadı", DEFAULT_REGISTERED_ROOTS) == "yap"
    assert match_registered_root("değiştirildi", DEFAULT_REGISTERED_ROOTS) == "değiştir"
    assert match_registered_root("bozuldu", DEFAULT_REGISTERED_ROOTS) == "bozul"
    assert match_registered_root("arıyor", DEFAULT_REGISTERED_ROOTS) == "ara"
    assert match_registered_root("bekliyor", DEFAULT_REGISTERED_ROOTS) == "bekle"

    # Non-verbs or unrelated nouns should not match
    assert match_registered_root("masa", DEFAULT_REGISTERED_ROOTS) is None
    assert match_registered_root("koltuk", DEFAULT_REGISTERED_ROOTS) is None

    # Sentence expression extraction
    sentence = "Servis gelmiyor, firma cevap vermiyor."
    matches = extract_registered_root_expressions(sentence, DEFAULT_REGISTERED_ROOTS)
    roots = [m[1] for m in matches]
    exprs = [m[0] for m in matches]
    assert "gel" in roots
    assert "ver" in roots
    assert "servis gelmiyor" in exprs
    assert "cevap vermiyor" in exprs

    # Find sentences from records
    records = [
        {"title": "Teslimat", "complaint_text": "Montaj yapıldı ancak parça eksik geldi.", "company": "istikbal", "complaint_date": "2026-09-28"},
        {"title": "Kumaş", "complaint_text": "Kumaş dikişi açıldı.", "company": "bellona", "complaint_date": "2026-09-29"},
    ]
    results = find_sentences_with_registered_roots(records)
    found_roots = {r.root for r in results}
    assert "yap" in found_roots
    assert "gel" in found_roots
    assert "aç" in found_roots
    assert any("montaj yapıldı" in r.expression for r in results)

