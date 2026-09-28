import json

from mobilitik.analysis.classifier import (
    classify_text,
    parse_rule_terms,
    reset_category_rules,
    set_category_rules,
)


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


def test_short_rule_does_not_match_inside_another_word():
    result = classify_text("Buraya kadar süreç normal ilerledi.")
    assert "Aksesuar / Donanım" not in result.categories


def test_rule_text_parser_supports_manual_weights_and_defaults():
    rules = parse_rule_terms("teslimat=3; geç teslim; servis gelmedi=4,5")
    assert rules["teslimat"] == 3.0
    assert rules["geç teslim"] == 2.0
    assert rules["servis gelmedi"] == 4.5


def test_manual_categories_can_be_activated_and_persisted(tmp_path):
    path = tmp_path / "categories.json"
    custom = {
        "Benim Teslimat Kategorim": {
            "geciken sevkiyat": 3.0,
            "teslim edilmedi": 2.0,
        }
    }
    try:
        set_category_rules(custom, persist=True, path=path)
        result = classify_text("Siparişim teslim edilmedi.")
        assert result.primary_category == "Benim Teslimat Kategorim"
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["Benim Teslimat Kategorim"]["geciken sevkiyat"] == 3.0
    finally:
        reset_category_rules()
