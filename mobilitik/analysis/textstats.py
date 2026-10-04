from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-zÇĞİIÖŞÜçğıöşü]+", re.UNICODE)
_TURKISH_LOWER_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})


def normalize_text(text: str) -> str:
    """Normalize whitespace and casing without destroying Turkish characters.

    Python's default lower-casing turns capital ``İ`` into ``i`` plus a
    combining dot. The old tokenizer then saw ``İstikbal`` as ``i`` +
    ``stikbal``. Translating Turkish I/İ before lower-casing keeps words intact.
    """
    value = unicodedata.normalize("NFC", text or "")
    value = value.translate(_TURKISH_LOWER_TRANSLATION).lower()
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip()


_RAW_STOPWORDS = {
    # Bağlaçlar ve edatlar
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "de", "da", "ki", "için", "ama", "ancak",
    "çok", "daha", "en", "gibi", "kadar", "sonra", "önce", "olan", "olarak", "ise", "diye",
    "çünkü", "fakat", "lakin", "halbuki", "oysa", "ayrıca", "hem", "ya", "yahut", "eğer",
    "şayet", "madem", "böylece", "dolayısıyla", "dolayı", "nedeniyle", "sebebiyle", "üzere", "göre",
    "karşı", "doğru", "itibaren", "beri", "boyunca", "esnasında", "sırasında", "birlikte", "beraber",
    "tarafından", "şekilde", "hakkında", "rağmen",

    # Zamirler ve işaret sözcükleri
    "ben", "biz", "siz", "onlar", "bana", "bizi", "beni", "bize", "size", "onlara",
    "benden", "bizden", "sizden", "onlardan", "benim", "bizim", "sizin", "onların",
    "bunun", "bunu", "buna", "bunda", "bundan", "şunun", "şunu", "şuna", "şunda", "şundan",
    "onun", "onu", "ona", "onda", "ondan", "bunlar", "şunlar", "burada", "şurada", "orada",
    "buraya", "şuraya", "oraya", "buradan", "oradan", "kendi", "kendisi", "kendim", "kendimiz",

    # Belirteçler ve sıklık sözcükleri
    "her", "tüm", "bütün", "bazı", "birkaç", "hiç", "hiçbir", "bile", "dahi", "yalnız", "sadece",
    "tekrar", "yine", "gene", "zaten", "artık", "hala", "hâlâ", "öyle", "şöyle", "böyle",
    "aynen", "tabi", "tabii", "acaba", "belki", "nasıl", "neden", "niçin", "niye", "hangi",

    # Şikayet bağlamında yaygın gürültü / yardımcı eylemler
    "şirket", "firma", "ürün", "aldım", "aldık", "ettim", "edildi", "ediyor", "eden", "ettiği",
    "etmek", "oldu", "oluyor", "olan", "olması", "olduğu", "olmak", "var", "yok", "yaptım",
    "yaptık", "yapıldı", "yapıyor", "yapan", "yaptığı", "yapmak", "dedim", "dedi", "demek",
    "verdi", "verdim", "verilen", "aldığı", "gelen", "giden",
}
STOPWORDS = {normalize_text(word) for word in _RAW_STOPWORDS}


def raw_tokens(text: str, min_len: int = 2) -> list[str]:
    """Tokenize Turkish text without stop-word removal."""
    normalized = normalize_text(text)
    tokens = [m.group(0) for m in TOKEN_RE.finditer(normalized)]
    return [token for token in tokens if len(token) >= min_len]


def tokenize(text: str, min_len: int = 3) -> list[str]:
    return [token for token in raw_tokens(text, min_len=min_len) if token not in STOPWORDS]


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

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [TermScore(term=term, score=score, count=term_freq[term]) for term, score in ranked]


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
        scored.sort(key=lambda item: item.score, reverse=True)
        result[group] = scored[:top_k]
    return result
