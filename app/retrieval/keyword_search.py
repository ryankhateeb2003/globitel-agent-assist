"""
TASK 5 — Hybrid Search and Reranking
File: app/retrieval/keyword_search.py
Purpose: Keyword-based (exact-match) search layer over the chunk corpus,
using the same Arabic normalization applied at ingestion time (Task 1)
so a normalized query matches normalized content. This is combined later
with vector search (Task 3's BGE-M3 index) via reciprocal rank fusion to
form the "hybrid" mode.
"""

import json
import re
from pathlib import Path

from app.ingestion.arabic_normalizer import normalize_arabic


def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def normalize_for_keyword_match(text: str) -> str:
    """
    Applies the same Arabic normalization used at ingestion (Task 1:
    alef unification, taa marbuta, tatweel removal, digit normalization)
    to both the query and the stored text, so a keyword match works
    regardless of orthographic variation (e.g. "اورنج" vs "أورانج").
    For English text, normalize_arabic() is a no-op passthrough.
    """
    return normalize_arabic(text).lower()


def tokenize(text: str) -> set[str]:
    """
    Simple whitespace/punctuation tokenizer. Keeps alphanumeric runs
    (including Arabic script) and short codes like "*140#" intact as
    single tokens where possible, since splitting "*140#" into "140"
    would lose the exact-match value that keyword search exists for.
    """
    normalized = normalize_for_keyword_match(text)
    # Keep USSD-style codes (*digits#) as one token, otherwise split on
    # whitespace and strip surrounding punctuation.
    tokens = re.findall(r"\*\d+#|[\w\u0600-\u06FF]+", normalized)
    return set(tokens)


_CHUNK_INDEX = None


def _build_index(chunks_path: str = "chunks.jsonl") -> list[dict]:
    """
    Precomputes the token set for every chunk once, so repeated keyword
    searches don't re-tokenize the whole corpus each call.
    """
    global _CHUNK_INDEX
    if _CHUNK_INDEX is None:
        chunks = load_chunks(chunks_path)
        for c in chunks:
            c["_tokens"] = tokenize(c["text"])
        _CHUNK_INDEX = chunks
    return _CHUNK_INDEX


def keyword_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Scores every chunk by token overlap with the query (normalized Jaccard
    -- intersection size over query token count), and returns the top_k
    highest-scoring chunks with score > 0.

    This is intentionally simple (no TF-IDF/BM25 weighting) for a first
    hybrid-search pass -- exact term overlap is what's needed to catch
    fees, codes, and limits that vector search misses; ranking
    sophistication can be added later if the comparison in
    hybrid-results.md shows it's needed.
    """
    chunks = _build_index()
    query_tokens = tokenize(query)

    if not query_tokens:
        return []

    scored = []
    for chunk in chunks:
        overlap = query_tokens & chunk["_tokens"]
        if not overlap:
            continue
        score = len(overlap) / len(query_tokens)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk in scored[:top_k]:
        results.append(
            {
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "language": chunk["language"],
                "topic": chunk["topic"],
                "source_file": chunk["source_file"],
                "score": round(score, 4),
            }
        )
    return results


if __name__ == "__main__":
    test_queries = [
        "*140#",
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