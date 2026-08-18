"""
Task 5 -- Keyword (lexical) search layer over the chunk corpus.

Combined later with vector search (Task 3's BGE-M3 index, via
app/rag/retrieval.py) through reciprocal rank fusion (see hybrid.py) to
form "hybrid" mode. Exists to catch exact values -- short codes, fees,
transfer limits -- that a vector search can miss, since embeddings
represent meaning, not exact tokens.

Arabic handling: every chunk and every query is passed through the same
normalize_arabic() used at ingestion time (Task 1) before tokenizing --
alef/taa-marbuta unification, tatweel/diacritic removal, digit
normalization. Without this, "اورنج" vs "أورانج" or "٩٧٩" vs "979" would
never match even though they mean the same thing. See
arabic-keyword-notes.md for concrete before/after proof.

Scoring: BM25 (Okapi), not plain token overlap. A previous version of this
module scored by Jaccard overlap (intersection / query token count), which
weights every matching word equally -- so a chunk matching only on common
words like "هل" or "كيف" could outscore one matching on the actual rare
term the query cares about (a short code, a proper noun). BM25's IDF term
downweights words that appear in most chunks and rewards rare,
high-signal matches, which is exactly the failure mode this hybrid layer
exists to fix.
"""

import json
import math
import re
from collections import Counter
from pathlib import Path

from app.ingestion.arabic_normalizer import normalize_arabic

# Standard Okapi BM25 constants (k1 controls term-frequency saturation,
# b controls document-length normalization strength). Not tuned against
# this corpus specifically -- these are the widely-used defaults.
_BM25_K1 = 1.5
_BM25_B = 0.75

_INDEX = None  # populated lazily by _build_index(): dict with chunks/df/avg_len


def normalize_for_keyword_match(text: str) -> str:
    """
    Same normalization path as ingestion (Task 1), applied to both the
    corpus text and every incoming query, lowercased on top so English
    matching is also case-insensitive. For pure-English text,
    normalize_arabic() is a no-op passthrough.
    """
    return normalize_arabic(text).lower()


def tokenize(text: str) -> list[str]:
    """
    Whitespace/punctuation tokenizer that keeps two things intact as
    single tokens instead of splitting them:
      - USSD-style short codes ("*979#") -- splitting would turn the one
        token this search exists to catch into meaningless fragments
        ("979").
      - Arabic script runs (\\u0600-\\u06FF), alongside plain word
        characters for English/digits.
    """
    normalized = normalize_for_keyword_match(text)
    return re.findall(r"\*\d+(?:\*\d+)*#|[\w؀-ۿ]+", normalized)


def load_chunks(path: str | Path = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _build_index(chunks_path: str | Path = "chunks.jsonl") -> dict:
    """
    Precomputes, once per process, everything BM25 needs: each chunk's
    term frequencies, document frequency per term across the whole
    corpus, and the average chunk length in tokens.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    chunks = load_chunks(chunks_path)
    doc_freq = Counter()
    total_len = 0

    for chunk in chunks:
        tokens = tokenize(chunk["text"])
        chunk["_tokens"] = tokens
        chunk["_term_freq"] = Counter(tokens)
        total_len += len(tokens)
        doc_freq.update(set(tokens))

    _INDEX = {
        "chunks": chunks,
        "doc_freq": doc_freq,
        "avg_len": (total_len / len(chunks)) if chunks else 0.0,
        "n_docs": len(chunks),
    }
    return _INDEX


def _idf(term: str, doc_freq: Counter, n_docs: int) -> float:
    df = doc_freq.get(term, 0)
    # +0.5 smoothing (standard Okapi BM25 idf) keeps this positive even
    # for terms that appear in most chunks, instead of going negative.
    return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))


def keyword_search(query: str, top_k: int = 5, chunks_path: str | Path = "chunks.jsonl") -> list[dict]:
    """
    BM25-ranks every chunk against the query's tokens and returns the
    top_k highest-scoring chunks with score > 0.

    Not filtered by language (consistent with Task 3's cross-language.md
    decision not to filter vector search by language either): a query
    containing a short code shared across both languages' pages should be
    able to surface either version, and /ask (Task 4) is where the answer
    language is actually enforced, not retrieval.
    """
    index = _build_index(chunks_path)
    query_tokens = tokenize(query)

    if not query_tokens:
        return []

    unique_query_terms = set(query_tokens)
    doc_freq = index["doc_freq"]
    n_docs = index["n_docs"]
    avg_len = index["avg_len"]

    scored = []
    for chunk in index["chunks"]:
        doc_len = len(chunk["_tokens"])
        term_freq = chunk["_term_freq"]

        score = 0.0
        for term in unique_query_terms:
            tf = term_freq.get(term, 0)
            if tf == 0:
                continue
            idf = _idf(term, doc_freq, n_docs)
            denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / avg_len)
            score += idf * (tf * (_BM25_K1 + 1)) / denom

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "language": chunk["language"],
            "topic": chunk["topic"],
            "source_file": chunk["source_file"],
            "score": round(score, 4),
        }
        for score, chunk in scored[:top_k]
    ]


if __name__ == "__main__":
    test_queries = [
        "*979#",
        "رصيد الطوارئ",
        "emergency credit",
        "شحن المحفظه بالبطاقه البنكيه",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        results = keyword_search(q, top_k=3)
        if not results:
            print("  No matches.")
        for r in results:
            print(f"  score={r['score']}  lang={r['language']}  source={r['source_file']}")
            print(f"    {r['text'][:80]}...")
