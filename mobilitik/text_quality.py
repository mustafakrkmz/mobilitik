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

# Firma cevapları bazen Şikayetvar'ın değişen DOM yapısı nedeniyle şikâyet
# gövdesiyle aynı geniş kapsayıcıdan okunabiliyor. Bunlar tüketici metni
# değildir ve metin madenciliği/NLP analizlerine girmemelidir.
COMPANY_RESPONSE_MARKERS = (
    "değerli müşterimiz, öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz",
    "değerli müşterimiz öncelikle firmamıza gösterdiğiniz ilgiye teşekkür ederiz",
    "talebiniz ilgili birimlere iletilmiş olup, tüketici hizmetleri yetkilimiz sizinle irtibata geçecektir",
    "talebiniz ilgili birimlere iletilmiş olup tüketici hizmetleri yetkilimiz sizinle irtibata geçecektir",
    "sayın ilgili tüketicimize gerekli bilgi aktarımı yapılmıştır",
    "markamıza göstermiş olduğunuz ilgi için öncelikle teşekkür ederiz",
    "markamıza göstermiş olduğunuz ilgi için teşekkür ederiz",
)


def normalize_space(value: str | None) -> str:
    return " ".join((value or "").split())


def _fold(value: str | None) -> str:
    return normalize_space(value).replace("I", "ı").replace("İ", "i").lower()


def is_boilerplate_complaint_text(value: str | None) -> bool:
    text = _fold(value)
    if not text:
        return False
    return any(marker in text for marker in BOILERPLATE_MARKERS)


def _response_start_index(text: str, company_response_text: str | None = None) -> int | None:
    """Return the earliest point where a company response starts in mixed text.

    Exact scraped company-response text has priority. Because HTML extraction can
    alter whitespace or append timestamps, we also try a stable prefix. Finally,
    well-known corporate response openings provide a DOM-independent fallback.
    """
    folded = _fold(text)
    if not folded:
        return None

    indices: list[int] = []
    response = _fold(company_response_text)
    if response:
        # Exact response may be present verbatim in a too-broad complaint container.
        idx = folded.find(response)
        if idx >= 0:
            indices.append(idx)
        # A response container may include extra trailing text; its opening is more stable.
        prefix = response[: min(len(response), 90)].strip()
        if len(prefix) >= 24:
            idx = folded.find(prefix)
            if idx >= 0:
                indices.append(idx)

    for marker in COMPANY_RESPONSE_MARKERS:
        idx = folded.find(marker)
        if idx >= 0:
            indices.append(idx)

    return min(indices) if indices else None


def sanitize_complaint_body(
    value: str | None,
    company_response_text: str | None = None,
) -> str:
    """Return only the consumer's initial complaint text.

    Known SEO preview copy is rejected entirely. If a too-broad selector returned
    the consumer complaint followed by a company answer, everything from the first
    identifiable company-response boundary onward is removed. If the selected text
    is itself only a company response, an empty string is returned so callers can
    fall back to the listing excerpt instead of analysing corporate boilerplate.
    """
    text = normalize_space(value)
    if not text or is_boilerplate_complaint_text(text):
        return ""

    response_index = _response_start_index(text, company_response_text)
    if response_index is not None:
        if response_index == 0:
            return ""
        text = text[:response_index].strip(" -–—|,;:")

    return normalize_space(text)


def analysis_text(
    title: str | None,
    body: str | None,
    company_response_text: str | None = None,
) -> str:
    """Return consumer-only analysis text, excluding platform/company boilerplate."""
    clean_title = normalize_space(title)
    clean_body = sanitize_complaint_body(body, company_response_text)
    return " ".join(part for part in (clean_title, clean_body) if part).strip()
