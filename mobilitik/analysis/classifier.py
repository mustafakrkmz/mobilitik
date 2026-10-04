from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mobilitik.config import DEFAULT_CATEGORIES_PATH
from mobilitik.text_quality import analysis_text


CATEGORY_RULES_PATH = DEFAULT_CATEGORIES_PATH

DEFAULT_CATEGORY_RULES: dict[str, dict[str, float]] = {
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


def _copy_rules(rules: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    return {
        str(category): {str(term): float(weight) for term, weight in terms.items()}
        for category, terms in rules.items()
        if str(category).strip()
    }


def _load_rules_file(path: Path) -> dict[str, dict[str, float]] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        parsed: dict[str, dict[str, float]] = {}
        for category, terms in data.items():
            if not isinstance(category, str) or not isinstance(terms, dict):
                continue
            parsed_terms: dict[str, float] = {}
            for term, weight in terms.items():
                if not isinstance(term, str):
                    continue
                try:
                    parsed_terms[term.strip()] = float(weight)
                except (TypeError, ValueError):
                    continue
            if category.strip() and parsed_terms:
                parsed[category.strip()] = parsed_terms
        return parsed or None
    except (OSError, json.JSONDecodeError):
        return None


_ACTIVE_RULES = _load_rules_file(CATEGORY_RULES_PATH) or deepcopy(DEFAULT_CATEGORY_RULES)


def get_category_rules() -> dict[str, dict[str, float]]:
    return deepcopy(_ACTIVE_RULES)


def set_category_rules(
    rules: Mapping[str, Mapping[str, float]],
    *,
    persist: bool = False,
    path: Path | None = None,
) -> dict[str, dict[str, float]]:
    global _ACTIVE_RULES
    cleaned = _copy_rules(rules)
    if not cleaned:
        raise ValueError("En az bir kategori ve anahtar ifade bulunmalıdır.")
    _ACTIVE_RULES = cleaned
    if persist:
        save_category_rules(cleaned, path=path)
    return get_category_rules()


def save_category_rules(
    rules: Mapping[str, Mapping[str, float]] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    destination = Path(path or CATEGORY_RULES_PATH)
    payload = _copy_rules(rules or _ACTIVE_RULES)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return destination


def reset_category_rules(*, persist: bool = False, path: Path | None = None) -> dict[str, dict[str, float]]:
    return set_category_rules(DEFAULT_CATEGORY_RULES, persist=persist, path=path)


def format_rule_terms(terms: Mapping[str, float]) -> str:
    """Human-editable ``ifade=ağırlık`` representation used by the GUI."""
    return "; ".join(f"{term}={weight:g}" for term, weight in terms.items())


def parse_rule_terms(value: str, *, default_weight: float = 2.0) -> dict[str, float]:
    """Parse ``ifade=3; başka ifade=2`` or plain semicolon-separated terms."""
    result: dict[str, float] = {}
    for raw_piece in (value or "").split(";"):
        piece = raw_piece.strip()
        if not piece:
            continue
        if "=" in piece:
            term, raw_weight = piece.rsplit("=", 1)
            term = term.strip()
            try:
                weight = float(raw_weight.strip().replace(",", "."))
            except ValueError as exc:
                raise ValueError(f"Geçersiz ağırlık: {piece}") from exc
        else:
            term = piece
            weight = default_weight
        if not term:
            continue
        if weight <= 0:
            raise ValueError("Kategori ağırlıkları sıfırdan büyük olmalıdır.")
        result[term] = weight
    return result


def _normalize(text: str) -> str:
    text = (text or "").replace("I", "ı").replace("İ", "i").lower()
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


def classify_text(
    text: str,
    *,
    threshold: float = 2.0,
    rules: Mapping[str, Mapping[str, float]] | None = None,
) -> ClassificationResult:
    normalized = _normalize(text or "")
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    active_rules = rules or _ACTIVE_RULES
    for category, category_rules in active_rules.items():
        score = 0.0
        hits: list[str] = []
        for phrase, weight in category_rules.items():
            if _contains_phrase(normalized, phrase):
                score += float(weight)
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
    return classify_text(analysis_text(title, body))
