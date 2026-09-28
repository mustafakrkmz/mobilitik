from mobilitik.analysis.textstats import TextAnalyzer, normalize_text, tokenize


def test_turkish_normalization_preserves_characters_and_dotted_i():
    assert normalize_text("Kırık Şifonyer Ürünü") == "kırık şifonyer ürünü"
    assert normalize_text("İstikbal") == "istikbal"
    assert tokenize("İstikbal teslimatı geciktiriyor")[:2] == ["istikbal", "teslimatı"]


def test_stopwords_removed_after_normalization():
    tokens = tokenize("Bu ürün teslimat için çok geç geldi")
    assert "ürün" not in tokens
    assert "için" not in tokens
    assert "teslimat" in tokens
    assert "geldi" in tokens


def test_bigram_frequency_and_document_frequency():
    analyzer = TextAnalyzer([
        "teslimat tarihi sürekli ertelendi",
        "teslimat tarihi yine değişti",
        "servis kaydı açıldı",
    ])
    top = dict(analyzer.top_ngrams(n=2, top_k=10))
    doc_freq = analyzer.document_frequency(n=2)
    assert top["teslimat tarihi"] == 2
    assert doc_freq["teslimat tarihi"] == 2


def test_tfidf_returns_terms_with_turkish_characters():
    analyzer = TextAnalyzer([
        "koltuk kumaşı yırtıldı",
        "koltuk kumaşı söküldü",
        "teslimat gecikti",
    ])
    terms = analyzer.tfidf(n=2, top_k=10, min_doc_freq=1)
    names = {item.term for item in terms}
    assert "koltuk kumaşı" in names


def test_trigrams_are_supported():
    analyzer = TextAnalyzer([
        "teknik servis kaydı açıldı",
        "teknik servis kaydı kapandı",
    ])
    top = dict(analyzer.top_ngrams(n=3, top_k=10))
    assert top["teknik servis kaydı"] == 2
