import pytest

from mobilitik.analysis.sentiment import (
    aggregate_aspect_sentiment,
    aspect_sentence_map,
    priority_score,
    scores_from_pipeline_output,
    sentiment_label_tr,
    split_sentences,
    text_fingerprint,
)


def test_scores_normalize_named_labels():
    result = scores_from_pipeline_output([
        {"label": "Negative", "score": 0.8},
        {"label": "Neutral", "score": 0.15},
        {"label": "Positive", "score": 0.05},
    ])
    assert result.label == "negative"
    assert result.confidence == pytest.approx(0.8)
    assert result.negative == pytest.approx(0.8)
    assert sentiment_label_tr(result.label) == "Negatif"


def test_scores_support_label_ids():
    result = scores_from_pipeline_output([
        {"label": "LABEL_0", "score": 0.1},
        {"label": "LABEL_1", "score": 0.2},
        {"label": "LABEL_2", "score": 0.7},
    ])
    assert result.label == "positive"
    assert result.positive == pytest.approx(0.7)


def test_scores_reject_unknown_output():
    with pytest.raises(ValueError):
        scores_from_pipeline_output([{"label": "mystery", "score": 1.0}])


def test_fingerprint_changes_with_text():
    first = text_fingerprint("Başlık", "Metin")
    second = text_fingerprint("Başlık", "Başka metin")
    assert first != second
    assert len(first) == 64


def test_sentence_split_and_manual_aspect_mapping():
    sentences = split_sentences("Teslimat gecikti. Montaj hatası var! Servis gelmiyor?")
    assert len(sentences) == 3
    mapped = aspect_sentence_map("", "Teslimat gecikti. Montaj hatası var.")
    categories = [category for _sentence, cats in mapped for category in cats]
    assert "Teslimat / Lojistik" in categories
    assert "Montaj / Servis" in categories


def test_aggregate_aspect_sentiment():
    delivery = scores_from_pipeline_output([
        {"label": "Negative", "score": 0.9},
        {"label": "Neutral", "score": 0.08},
        {"label": "Positive", "score": 0.02},
    ])
    service = scores_from_pipeline_output([
        {"label": "Negative", "score": 0.6},
        {"label": "Neutral", "score": 0.3},
        {"label": "Positive", "score": 0.1},
    ])
    result = {row.category: row for row in aggregate_aspect_sentiment([
        (["Teslimat / Lojistik"], delivery),
        (["Teslimat / Lojistik", "Montaj / Servis"], service),
    ])}
    assert result["Teslimat / Lojistik"].sentence_count == 2
    assert result["Teslimat / Lojistik"].negative == pytest.approx(0.75)
    assert result["Montaj / Servis"].negative == pytest.approx(0.6)


def test_priority_score_is_transparent_and_weighted():
    score = priority_score(0.5, 0.8, 0.4)
    assert score == pytest.approx((0.5 * 40 + 0.8 * 35 + 0.4 * 25))
    assert priority_score(1, 1, 1) == pytest.approx(100.0)
    assert priority_score(0, 0, 0) == 0.0
    assert priority_score(1, 1, 1, frequency_weight=0, negativity_weight=0, unresolved_weight=0) == 0.0
    with pytest.raises(ValueError):
        priority_score(1, 1, 1, frequency_weight=-1)
