from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from mobilitik.analysis.textstats import normalize_text, raw_tokens
from mobilitik.text_quality import analysis_text


@dataclass(frozen=True)
class ContextHit:
    context: str
    count: int
    document_count: int
    anchor_share: float
    period_share: float


def _anchor_tokens(anchor: str) -> tuple[str, ...]:
    pieces = [piece.strip() for piece in normalize_text(anchor).split() if piece.strip()]
    if not pieces:
        return ()
    return tuple(pieces)


def _token_matches(token: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        return bool(prefix) and token.startswith(prefix)
    return token == pattern


def _anchor_at(tokens: list[str], start: int, patterns: tuple[str, ...]) -> bool:
    if start < 0 or start + len(patterns) > len(tokens):
        return False
    return all(_token_matches(tokens[start + offset], pattern) for offset, pattern in enumerate(patterns))


def _contexts_for_tokens(
    tokens: list[str],
    patterns: tuple[str, ...],
    *,
    direction: str,
    window: int,
) -> list[str]:
    results: list[str] = []
    anchor_len = len(patterns)
    for index in range(0, len(tokens) - anchor_len + 1):
        if not _anchor_at(tokens, index, patterns):
            continue
        if direction == "left":
            context_tokens = tokens[max(0, index - window) : index]
            if context_tokens:
                results.append(" ".join(context_tokens))
        elif direction == "right":
            context_tokens = tokens[index + anchor_len : index + anchor_len + window]
            if context_tokens:
                results.append(" ".join(context_tokens))
        elif direction == "both":
            left = tokens[max(0, index - window) : index]
            right = tokens[index + anchor_len : index + anchor_len + window]
            if left or right:
                left_text = " ".join(left) if left else "∅"
                right_text = " ".join(right) if right else "∅"
                results.append(f"{left_text}  ←  [{normalize_text(' '.join(patterns)).replace('*', '…')}]  →  {right_text}")
        else:
            raise ValueError("direction must be left, right or both")
    return results


def analyze_context(
    records: Iterable[Mapping[str, Any]],
    anchor: str,
    *,
    direction: str = "left",
    window: int = 1,
    min_count: int = 1,
    top_k: int = 50,
) -> tuple[list[ContextHit], dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Analyse lexical context around an anchor phrase in consumer-only text.

    ``anchor`` may contain more than one token. A trailing ``*`` means prefix
    matching, e.g. ``bayi*`` matches ``bayi``, ``bayiden`` and ``bayisinden``.
    Counts are occurrence counts; document_count counts unique complaints.
    ``anchor_share`` is the share among complaints containing the anchor, while
    ``period_share`` is the share among all selected complaints.
    """
    if window < 1 or window > 10:
        raise ValueError("window must be between 1 and 10")
    if min_count < 1:
        raise ValueError("min_count must be at least 1")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    patterns = _anchor_tokens(anchor)
    if not patterns:
        return [], {}, {"records": 0, "anchor_documents": 0, "anchor_mentions": 0, "unique_contexts": 0}

    source = [dict(record) for record in records]
    counts: Counter[str] = Counter()
    doc_sets: dict[str, set[int]] = defaultdict(set)
    context_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    anchor_document_ids: set[int] = set()
    anchor_mentions = 0

    for record_index, record in enumerate(source):
        text = analysis_text(
            record.get("title"),
            record.get("complaint_text"),
            record.get("company_response_text"),
        )
        tokens = raw_tokens(text, min_len=1)
        contexts = _contexts_for_tokens(tokens, patterns, direction=direction, window=window)
        if not contexts:
            continue
        anchor_document_ids.add(record_index)
        anchor_mentions += len(contexts)
        for context in contexts:
            counts[context] += 1
            doc_sets[context].add(record_index)

    total_records = len(source)
    anchor_documents = len(anchor_document_ids)
    ranked_contexts = [
        context for context, count in counts.most_common()
        if count >= min_count
    ][:top_k]

    for context in ranked_contexts:
        context_records[context] = [source[index] for index in sorted(doc_sets[context])]

    hits = [
        ContextHit(
            context=context,
            count=counts[context],
            document_count=len(doc_sets[context]),
            anchor_share=(len(doc_sets[context]) / anchor_documents) if anchor_documents else 0.0,
            period_share=(len(doc_sets[context]) / total_records) if total_records else 0.0,
        )
        for context in ranked_contexts
    ]
    meta = {
        "records": total_records,
        "anchor_documents": anchor_documents,
        "anchor_mentions": anchor_mentions,
        "unique_contexts": len(counts),
    }
    return hits, dict(context_records), meta
