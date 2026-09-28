from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", re.UNICODE)

STOPWORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "de", "da", "ki", "için", "ama", "ancak",
    "çok", "daha", "en", "gibi", "kadar", "sonra", "önce", "olan", "olarak", "ise", "ben", "biz",
    "siz", "onlar", "bana", "bizi", "beni", "bunun", "bunu", "şirket", "firma", "ürün", "aldım",
    "aldık", "ettim", "edildi", "ediyor", "oldu", "oluyor", "var", "yok", "hala", "artık",
}


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = (
        text.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str, min_len: int = 3) -> list[str]:
    normalized = normalize_text(text)
    tokens = [m.group(0) for m in TOKEN_RE.finditer(normalized)]
    return [t for t in tokens if len(t) >= min_len and t not in STOPWORDS]


def ngrams(tokens: list[str], n: int) -> list[str]:
    if n <= 0:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


@dataclass
class TermScore:
    term: str
    score: float
    count: int


class TextAnalyzer:
    def __init__(self, documents: Iterable[str]):
        self.documents = [d or "" for d in documents]
        self.tokenized = [tokenize(d) for d in self.documents]

    def top_ngrams(self, n: int = 1, top_k: int = 30) -> list[tuple[str, int]]:
        counter: Counter[str] = Counter()
        for tokens in self.tokenized:
            counter.update(ngrams(tokens, n))
        return counter.most_common(top_k)

    def document_frequency(self, n: int = 1) -> Counter[str]:
        counter: Counter[str] = Counter()
        for tokens in self.tokenized:
            counter.update(set(ngrams(tokens, n)))
        return counter

    def tfidf(self, n: int = 1, top_k: int = 30, min_doc_freq: int = 2) -> list[TermScore]:
        doc_terms: list[list[str]] = [ngrams(tokens, n) for tokens in self.tokenized]
        doc_freq: Counter[str] = Counter()
        term_freq: Counter[str] = Counter()

        for terms in doc_terms:
            counts = Counter(terms)
            term_freq.update(counts)
            doc_freq.update(counts.keys())

        doc_count = max(len(doc_terms), 1)
        scores: dict[str, float] = defaultdict(float)
        for term, tf in term_freq.items():
            df = doc_freq[term]
            if df < min_doc_freq:
                continue
            idf = math.log((1 + doc_count) / (1 + df)) + 1.0
            scores[term] = tf * idf

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [TermScore(term=t, score=s, count=term_freq[t]) for t, s in ranked]


def distinctive_terms(grouped_documents: dict[str, list[str]], n: int = 1, top_k: int = 15) -> dict[str, list[TermScore]]:
    """Return terms that are comparatively distinctive for each group."""
    group_term_counts: dict[str, Counter[str]] = {}
    group_presence: Counter[str] = Counter()

    for group, docs in grouped_documents.items():
        counter: Counter[str] = Counter()
        for doc in docs:
            counter.update(ngrams(tokenize(doc), n))
        group_term_counts[group] = counter
        group_presence.update(counter.keys())

    group_count = max(len(grouped_documents), 1)
    result: dict[str, list[TermScore]] = {}
    for group, counter in group_term_counts.items():
        scored: list[TermScore] = []
        for term, count in counter.items():
            presence = group_presence[term]
            idf = math.log((1 + group_count) / (1 + presence)) + 1.0
            scored.append(TermScore(term, count * idf, count))
        scored.sort(key=lambda x: x.score, reverse=True)
        result[group] = scored[:top_k]
    return result
