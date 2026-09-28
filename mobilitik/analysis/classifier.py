from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


CATEGORY_RULES: dict[str, dict[str, float]] = {
    "Teslimat / Lojistik": {
        "teslimat": 3.0,
        "teslim edilmedi": 4.0,
        "gecikti": 3.0,
        "gecikme": 3.0,
        "sevkiyat": 3.0,
        "kargo": 2.0,
        "nakliye": 2.5,
        "depoda": 1.5,
        "gelmedi": 2.5,
        "teslim tarihi": 3.0,
    },
    "Üretim / Kalite": {
        "kırık": 2.5,
        "çatlak": 2.5,
        "deforme": 3.0,
        "yamuk": 2.5,
        "eğri": 2.0,
        "çizik": 2.0,
        "boya": 1.5,
        "kaplama": 2.0,
        "yüzey": 1.5,
        "renk farkı": 2.5,
        "kumaş": 1.5,
        "sünger": 1.5,
        "dikiş": 1.5,
        "imalat": 3.0,
        "üretim hatası": 4.0,
        "kalite": 1.5,
    },
    "Aksesuar / Donanım": {
        "menteşe": 3.0,
        "ray": 2.5,
        "kulp": 2.5,
        "vida": 2.0,
        "mekanizma": 3.0,
        "amortisör": 3.0,
        "yay": 1.5,
        "ayak": 1.5,
        "aksesuar": 3.0,
        "donanım": 3.0,
    },
    "Montaj / Servis": {
        "montaj": 3.5,
        "kurulum": 3.0,
        "servis": 2.0,
        "teknik servis": 3.0,
        "usta": 1.5,
        "ekip gelmedi": 3.0,
        "montaj hatası": 4.0,
        "servis kaydı": 2.5,
    },
    "İade / Ücret": {
        "iade": 3.0,
        "para iadesi": 4.0,
        "ücret iadesi": 4.0,
        "iptal": 2.0,
        "cayma": 2.5,
        "geri ödeme": 4.0,
        "bedel": 1.0,
    },
    "Satış / İletişim": {
        "müşteri hizmetleri": 2.5,
        "ulaşamıyorum": 2.5,
        "dönüş yapılmadı": 3.0,
        "geri dönüş": 1.5,
        "mağaza": 1.5,
        "satış danışmanı": 2.0,
        "yanlış bilgi": 2.5,
        "iletişim": 2.0,
    },
}


def _normalize(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"[^\wçğıöşü\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = _normalize(phrase)
    if not normalized_phrase:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)"
    return re.search(pattern, normalized_text, flags=re.UNICODE) is not None


@dataclass(frozen=True)
class ClassificationResult:
    primary_category: str
    scores: dict[str, float]
    matched_terms: dict[str, list[str]]

    @property
    def categories(self) -> list[str]:
        return [name for name, score in self.scores.items() if score > 0]


def classify_text(text: str, *, threshold: float = 2.0) -> ClassificationResult:
    normalized = _normalize(text or "")
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    for category, rules in CATEGORY_RULES.items():
        score = 0.0
        hits: list[str] = []
        for phrase, weight in rules.items():
            if _contains_phrase(normalized, phrase):
                score += weight
                hits.append(phrase)
        if score >= threshold:
            scores[category] = round(score, 2)
            matched[category] = hits

    if not scores:
        return ClassificationResult("Diğer", {}, {})

    primary = max(scores.items(), key=lambda item: item[1])[0]
    ordered_scores = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))
    ordered_hits = {category: matched[category] for category in ordered_scores}
    return ClassificationResult(primary, ordered_scores, ordered_hits)


def classify_record(title: str | None, body: str | None) -> ClassificationResult:
    parts: Iterable[str] = [part for part in (title, body) if part]
    return classify_text(" ".join(parts))
