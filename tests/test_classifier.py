from mobilitik.analysis.classifier import classify_text


def test_delivery_complaint():
    result = classify_text("Ürün teslim edilmedi, teslimat tarihi geçti ve sevkiyat hâlâ yapılmadı.")
    assert result.primary_category == "Teslimat / Lojistik"
    assert "Teslimat / Lojistik" in result.categories


def test_accessory_complaint():
    result = classify_text("Dolabın menteşesi ve ray mekanizması bozuk geldi.")
    assert result.primary_category == "Aksesuar / Donanım"


def test_manufacturing_complaint():
    result = classify_text("Masa yüzeyinde çatlak, çizik ve belirgin renk farkı var.")
    assert result.primary_category == "Üretim / Kalite"


def test_multi_category_complaint():
    result = classify_text("Teslimat gecikti, ürün geldiğinde montaj hatası vardı ve servis kaydı açıldı.")
    assert "Teslimat / Lojistik" in result.categories
    assert "Montaj / Servis" in result.categories


def test_unknown_goes_to_other():
    result = classify_text("Bu deneyimden genel olarak memnun kalmadım.")
    assert result.primary_category == "Diğer"
    assert result.categories == []
