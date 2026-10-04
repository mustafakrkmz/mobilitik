from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .textstats import normalize_text, raw_tokens


DEFAULT_VERB_SUFFIXES = ("ıyor", "iyor", "uyor", "üyor")
_PERSON_ENDINGS = ("sunuz", "sınız", "siniz", "sunuz", "sünüz", "lar", "ler", "nız", "niz", "nuz", "nüz", "sun", "sın", "sin", "m", "n", "k", "uz", "üz", "um", "üm")

# Backward-compatible progressive matcher used by extract_progressive_verb.
_PROGRESSIVE_RE = re.compile(
    r"^(?P<stem>[a-zçğıöşü]{2,}?)(?P<suffix>ıyor|iyor|uyor|üyor)"
    r"(?P<ending>um|üm|sun|uz|üz|sunuz|sünüz|lar|ler|m|n|k|nız|niz|nuz|nüz)?$",
    re.UNICODE,
)


@dataclass(frozen=True)
class VerbStat:
    stem: str
    count: int
    document_count: int
    examples: tuple[str, ...]


def parse_suffix_conditions(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize user supplied suffix conditions.

    ``-ıldı; -ildi`` and ``ıldı, ildi`` are both accepted. Duplicate suffixes
    are removed while preserving the user's order.
    """
    if value is None:
        return DEFAULT_VERB_SUFFIXES
    if isinstance(value, str):
        parts = re.split(r"[;,\n]+", value)
    else:
        parts = list(value)

    result: list[str] = []
    for part in parts:
        suffix = normalize_text(str(part)).strip().lstrip("-")
        suffix = re.sub(r"[^a-zçğıöşü]", "", suffix)
        if len(suffix) < 2 or suffix in result:
            continue
        result.append(suffix)
    return tuple(result) or DEFAULT_VERB_SUFFIXES


def extract_progressive_verb(token: str) -> str | None:
    """Return an approximate verb stem for Turkish progressive forms.

    This is intentionally a transparent heuristic, not a full morphological
    analyzer. For example ``geliyor`` -> ``gel`` and ``gidiyor`` -> ``gid``.
    Forms where Turkish drops a final vowel (e.g. ``bekliyor``) may yield a
    surface stem such as ``bekl``; the UI labels this as an approximate stem.
    """
    match = _PROGRESSIVE_RE.match(normalize_text(token))
    if not match:
        return None
    stem = match.group("stem")
    return stem if len(stem) >= 2 else None


def extract_by_suffix(token: str, suffixes: str | Iterable[str] | None = None) -> tuple[str, str] | None:
    """Return ``(approximate_stem, matched_suffix)`` for configured endings.

    Common person/number endings are tolerated after the configured suffix,
    so ``yapıldım`` matches the ``ıldı`` condition and ``geliyorum`` matches
    ``iyor``. This remains a surface-form heuristic rather than a lemmatizer.
    """
    word = normalize_text(token).strip()
    if not word:
        return None
    for suffix in sorted(parse_suffix_conditions(suffixes), key=len, reverse=True):
        suffix_index = word.rfind(suffix)
        if suffix_index < 2:
            continue
        tail = word[suffix_index + len(suffix):]
        if tail and tail not in _PERSON_ENDINGS:
            continue
        if suffix_index + len(suffix) + len(tail) != len(word):
            continue
        stem = word[:suffix_index]
        if len(stem) >= 2:
            return stem, suffix
    return None


def suffix_verb_stats(
    documents: Iterable[str],
    suffixes: str | Iterable[str] | None = None,
    top_k: int = 100,
) -> list[VerbStat]:
    """Count tokens matching configurable Turkish suffix conditions."""
    parsed_suffixes = parse_suffix_conditions(suffixes)
    counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    examples: dict[str, Counter[str]] = defaultdict(Counter)

    for document in documents:
        seen_in_document: set[str] = set()
        for token in raw_tokens(document or "", min_len=3):
            match = extract_by_suffix(token, parsed_suffixes)
            if not match:
                continue
            stem, _suffix = match
            counts[stem] += 1
            examples[stem][token] += 1
            seen_in_document.add(stem)
        document_counts.update(seen_in_document)

    rows: list[VerbStat] = []
    for stem, count in counts.most_common(top_k):
        common_examples = tuple(token for token, _ in examples[stem].most_common(5))
        rows.append(
            VerbStat(
                stem=stem,
                count=count,
                document_count=document_counts[stem],
                examples=common_examples,
            )
        )
    return rows


def progressive_verb_stats(documents: Iterable[str], top_k: int = 100) -> list[VerbStat]:
    """Backward-compatible wrapper for the default progressive suffixes."""
    return suffix_verb_stats(documents, DEFAULT_VERB_SUFFIXES, top_k=top_k)


# ----------------------------------------------------------------------
# Registered roots verb analysis & sentence listing
# ----------------------------------------------------------------------

DEFAULT_REGISTERED_ROOTS: tuple[str, ...] = (
    "gel", "git", "yap", "et", "ol", "al", "ver", "çık", "ara", "sor",
    "çöz", "kur", "dur", "kal", "dön", "bak", "gör", "bekle", "ulaş",
    "bil", "bul", "getir", "götür", "değiş", "değiştir", "boz", "bozul",
    "kır", "kırıl", "kes", "aç", "kapat", "öde", "iste", "duy", "anla",
    "yaz", "sat", "gönder", "tak", "taşı", "incele", "temizle", "yanıtla",
    "ilet", "görüş", "başla", "bitir", "onayla", "reddet",
)

# Turkish verb inflection suffix pattern to ensure the tail is a verb conjugation
_VERB_TAIL_RE = re.compile(
    r"^(m[ıiuü]yor|[ıiuü]?yor|m[ae]d[ıiuü]|m[ae]z|m[ae]y[ae]c[ae]k|m[ae]m[ıiuü]ş|"
    r"d[ıiuü]|t[ıiuü]|m[ıiuü]ş|[ae]c[ae]k|[ıiuü]r|[ae]r|m[ae]l[ıi]|"
    r"([ıiuü]l|[ıiuü]n|[dt][ıiuü]r)|[ae]b[ıi]l|[ae]m[ae]z|[ae]m[ae]d[ıi]|"
    r"m[ae]k|m[ae]y[ae]|m[ae]d[ae]n|[ıiuü]p|[ae]r[ae]k|[ıiuü]nc[ae]|d[ıik]ç[ae]|d[ıik]t[ae]|"
    r"[ae]n|[ıiuü]c[ıi]|d[ıiuü]ğ[ıiuü]|t[ıiuü]k|d[ıiuü]k|m[ae])*"
    r"(um|üm|sun|uz|üz|sunuz|sünüz|lar|ler|m|n|k|nız|niz|nuz|nüz|"
    r"[ıiuü]m|[ıiuü]z|[ıiuü]n|[ıiuü]n[ıiuü]z)?$",
    re.UNICODE,
)


@dataclass(frozen=True)
class VerbSentenceMatch:
    sentence: str
    root: str
    expression: str
    matched_token: str
    record: dict
    company: str
    date: str
    title: str


def parse_registered_roots(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize user supplied registered root conditions.

    Accepts semicolon, comma or newline separated strings or iterables.
    """
    if value is None:
        return DEFAULT_REGISTERED_ROOTS
    if isinstance(value, str):
        parts = re.split(r"[;,\n]+", value)
    else:
        parts = list(value)

    result: list[str] = []
    for part in parts:
        root = normalize_text(str(part)).strip().lstrip("-")
        root = re.sub(r"[^a-zçğıöşü]", "", root)
        if len(root) < 2 or root in result:
            continue
        result.append(root)
    return tuple(result) or DEFAULT_REGISTERED_ROOTS


def _generate_root_variants(root: str) -> list[tuple[str, str]]:
    """Return pairs of ``(stem_variant, canonical_root)`` handling Turkish phonology."""
    variants = [(root, root)]
    # Consonant softening for stems ending in t
    if root.endswith("t"):
        variants.append((root[:-1] + "d", root))
    # Vowel dropping / narrowing for stems ending in a/e before -iyor
    if root.endswith("a") or root.endswith("e"):
        base = root[:-1]
        narrow_vowels = ["ı", "i", "u", "ü"]
        for nv in narrow_vowels:
            variants.append((base + nv, root))
        variants.append((base, root))
    # Common passive/causative extensions
    if root in ("yap", "çöz", "kır", "kur", "boz", "al", "ver", "tak", "aç"):
        for ext in ("ıl", "il", "ul", "ül", "ın", "in", "un", "ün"):
            variants.append((root + ext, root))
    return variants


def match_registered_root(token: str, roots: Iterable[str]) -> str | None:
    """Check if ``token`` is an inflected verb derived from one of ``roots``."""
    word = normalize_text(token).strip()
    if len(word) < 2:
        return None

    # Sort roots by length descending to match longer specific roots first (e.g. değiştir before değiş)
    sorted_roots = sorted(roots, key=len, reverse=True)
    for root in sorted_roots:
        for prefix, canonical in _generate_root_variants(root):
            if word == prefix:
                return canonical
            if word.startswith(prefix):
                tail = word[len(prefix):]
                # Tail must match valid Turkish verbal suffix morphology
                if _VERB_TAIL_RE.match(tail):
                    return canonical
    return None


def extract_registered_root_expressions(
    sentence: str,
    roots: Iterable[str],
) -> list[tuple[str, str, str]]:
    """Extract ``(matched_expression, root, matched_token)`` from a sentence.

    If a verb matching a registered root is preceded by an object, modifier
    or auxiliary partner, the full phrase (e.g. ``servis gelmiyor`` or
    ``teslimat yapıldı``) is returned as the expression.
    """
    from .textstats import TOKEN_RE
    normalized = normalize_text(sentence)
    matches: list[tuple[str, str, str]] = []
    tokens = [m.group(0) for m in TOKEN_RE.finditer(normalized)]

    for idx, token in enumerate(tokens):
        matched_root = match_registered_root(token, roots)
        if not matched_root:
            continue
        # Check previous token to form a 2-word expression ending with the verb
        if idx > 0:
            prev_token = tokens[idx - 1]
            # Exclude grammatical conjunctions/prepositions
            if prev_token not in ("ve", "veya", "ile", "ama", "fakat", "ancak", "çünkü", "de", "da", "ki", "ise", "diye", "bu", "şu", "o", "bir"):
                expr = f"{prev_token} {token}"
            else:
                expr = token
        else:
            expr = token
        matches.append((expr, matched_root, token))

    return matches


def find_sentences_with_registered_roots(
    records: Iterable[dict],
    roots: Iterable[str] | None = None,
    filter_root: str | None = None,
    query: str | None = None,
) -> list[VerbSentenceMatch]:
    """Scan complaint records and return all sentences containing expressions ending with registered roots."""
    from mobilitik.analysis.sentiment import split_sentences
    from mobilitik.text_quality import analysis_text

    parsed_roots = parse_registered_roots(roots)
    filter_root_norm = normalize_text(filter_root).strip() if filter_root and filter_root != "Tümü" else None
    query_norm = normalize_text(query).strip() if query else None

    results: list[VerbSentenceMatch] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for record in records:
        text = analysis_text(
            record.get("title"),
            record.get("complaint_text"),
            record.get("company_response_text"),
        )
        sentences = split_sentences(text)
        company = str(record.get("company") or "")
        date = str(record.get("complaint_date") or "")
        title = str(record.get("title") or "")

        for sentence in sentences:
            sentence_norm = normalize_text(sentence)
            if query_norm and query_norm not in sentence_norm:
                continue

            expr_matches = extract_registered_root_expressions(sentence, parsed_roots)
            for expr, root, token in expr_matches:
                if filter_root_norm and root != filter_root_norm:
                    continue
                key = (sentence, root, expr)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                results.append(
                    VerbSentenceMatch(
                        sentence=sentence,
                        root=root,
                        expression=expr,
                        matched_token=token,
                        record=record,
                        company=company,
                        date=date,
                        title=title,
                    )
                )

    return results

