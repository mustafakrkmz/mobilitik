from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .textstats import raw_tokens


# Focused deliberately on the present-continuous forms requested by the UI:
# -ıyor / -iyor / -uyor / -üyor and common person/number endings.
_PROGRESSIVE_RE = re.compile(
    r"^(?P<stem>[a-zçğıöşü]{2,}?)(?P<suffix>ıyor|iyor|uyor|üyor)"
    r"(?P<ending>um|sun|uz|sunuz|lar|m|n|k|nız|niz|nuz|nüz)?$",
    re.UNICODE,
)


@dataclass(frozen=True)
class VerbStat:
    stem: str
    count: int
    document_count: int
    examples: tuple[str, ...]


def extract_progressive_verb(token: str) -> str | None:
    """Return an approximate verb stem for Turkish progressive forms.

    This is intentionally a transparent heuristic, not a full morphological
    analyzer. For example ``geliyor`` -> ``gel`` and ``gidiyor`` -> ``gid``.
    Forms where Turkish drops a final vowel (e.g. ``bekliyor``) may yield a
    surface stem such as ``bekl``; the UI labels this as an approximate stem.
    """
    match = _PROGRESSIVE_RE.match(token)
    if not match:
        return None
    stem = match.group("stem")
    return stem if len(stem) >= 2 else None


def progressive_verb_stats(documents: Iterable[str], top_k: int = 100) -> list[VerbStat]:
    counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    examples: dict[str, Counter[str]] = defaultdict(Counter)

    for document in documents:
        seen_in_document: set[str] = set()
        for token in raw_tokens(document or "", min_len=3):
            stem = extract_progressive_verb(token)
            if not stem:
                continue
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
