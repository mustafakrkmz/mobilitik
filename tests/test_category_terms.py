from mobilitik.analysis.category_terms import category_distinctive_terms


def test_category_distinctive_terms_separates_delivery_and_quality():
    rows = [
        {
            "title": "Teslimat gecikti",
            "complaint_text": "Teslimat tarihi iki kez ertelendi ve sevkiyat yapılmadı.",
        },
        {
            "title": "Teslimat yine gecikti",
            "complaint_text": "Teslimat tarihi sürekli değişiyor, kargo gelmedi.",
        },
        {
            "title": "Koltuk kumaşı yırtıldı",
            "complaint_text": "Kumaş dikişleri açıldı ve üretim hatası olduğunu düşünüyorum.",
        },
        {
            "title": "Kumaş kalitesi kötü",
            "complaint_text": "Koltuk kumaşı kısa sürede deforme oldu ve dikiş söküldü.",
        },
    ]

    result = category_distinctive_terms(rows, n=2, top_k=20)

    assert "Teslimat / Lojistik" in result
    assert "Üretim / Kalite" in result
    delivery_terms = {item.term for item in result["Teslimat / Lojistik"]}
    quality_terms = {item.term for item in result["Üretim / Kalite"]}
    assert "teslimat tarihi" in delivery_terms
    assert "koltuk kumasi" in quality_terms


def test_category_distinctive_terms_empty_input():
    assert category_distinctive_terms([]) == {}
