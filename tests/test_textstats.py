from mobilitik.analysis.textstats import TextAnalyzer, normalize_text, tokenize


def test_turkish_normalization():
    assert normalize_text("Kırık Şifonyer Ürünü") == "kirik sifonyer urunu"


def test_stopwords_removed():
    tokens = tokenize("Bu ürün teslimat için çok geç geldi")
    assert "urun" not in tokens
    assert "icin" not in tokens
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


def test_tfidf_returns_terms():
    analyzer = TextAnalyzer([
        "koltuk kumaşı yırtıldı",
        "koltuk kumaşı söküldü",
        "teslimat gecikti",
    ])
    terms = analyzer.tfidf(n=2, top_k=10, min_doc_freq=1)
    names = {item.term for item in terms}
    assert "koltuk kumasi" in names
