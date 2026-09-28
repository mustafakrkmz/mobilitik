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
