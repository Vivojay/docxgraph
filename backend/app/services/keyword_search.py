from collections import Counter
from difflib import SequenceMatcher
import math
import re


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def bm25_lite_score(query: str, document: str) -> float:
    query_tokens = tokenize(query)
    doc_tokens = tokenize(document)
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    tf = Counter(doc_tokens)
    avg_doc_len = max(doc_len, 1)
    score = 0.0
    k1 = 1.2
    b = 0.75
    for token in query_tokens:
        freq = tf.get(token, 0)
        if freq == 0:
            continue
        numerator = freq * (k1 + 1)
        denominator = freq + k1 * (1 - b + b * (doc_len / avg_doc_len))
        score += numerator / denominator
    return score / max(len(query_tokens), 1)


def fuzzy_ratio(query: str, document: str) -> float:
    if not query or not document:
        return 0.0
    return SequenceMatcher(None, query.lower(), document.lower()).ratio()


def keyword_overlap_score(query: str, document: str) -> float:
    q = set(tokenize(query))
    d = set(tokenize(document))
    if not q or not d:
        return 0.0
    return len(q & d) / len(q)


def normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if math.isclose(minimum, maximum):
        return [1.0 if value > 0 else 0.0 for value in values]
    return [(value - minimum) / (maximum - minimum) for value in values]
