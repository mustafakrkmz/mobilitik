from __future__ import annotations


BOILERPLATE_MARKERS = (
    "şikayetini ve yorumlarını okumak",
    "şikâyetini ve yorumlarını okumak",
    "hakkında şikayet yazmak için tıklayın",
    "hakkında şikâyet yazmak için tıklayın",
    "şikayetleri için tıklayın",
    "şikâyetleri için tıklayın",
    "visit to read complaints and reviews",
    "file yours",
)


def normalize_space(value: str | None) -> str:
    return " ".join((value or "").split())


def is_boilerplate_complaint_text(value: str | None) -> bool:
    text = normalize_space(value).lower()
    if not text:
        return False
    return any(marker in text for marker in BOILERPLATE_MARKERS)


def sanitize_complaint_body(value: str | None) -> str:
    text = normalize_space(value)
    if not text or is_boilerplate_complaint_text(text):
        return ""
    return text


def analysis_text(title: str | None, body: str | None) -> str:
    """Return analysis text while excluding known Sikayetvar SEO preview copy."""
    clean_title = normalize_space(title)
    clean_body = sanitize_complaint_body(body)
    return " ".join(part for part in (clean_title, clean_body) if part).strip()
