"""
Task 5, optimization 1 of 3+: cache identical and near-identical questions.

Checked before any Groq call -- an exact repeat, or a different wording
of a question close enough in meaning (cosine similarity on its
embedding), returns the stored answer immediately. Skips retrieval,
the guardrail classifier, and generation entirely -- the whole point is
a contact center asks the same handful of questions over and over, so
most repeats should cost nothing.

Persisted to a file (not just in memory) so a server restart -- or
closing the laptop -- doesn't throw the cache away.
"""

import json
import re
from pathlib import Path

CACHE_PATH = Path("cache/qa_cache.jsonl")

# Balanced per project decision: high enough that two genuinely different
# questions essentially never collide, low enough that a reworded repeat
# ("how do I check my balance" vs "how can I see my balance") still hits.
SIMILARITY_THRESHOLD = 0.93

# Loaded once at process start, appended to in memory + on disk as new
# answers come in. A plain list is fine at this scale (a few hundred to
# a few thousand entries) -- no need for a real vector index here.
_cache: list[dict] = []
_loaded = False


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _ensure_loaded() -> None:
    """Lazy load so importing this module never touches disk by itself --
    only the first real cache check/store does."""
    global _loaded
    if _loaded:
        return
    if CACHE_PATH.exists():
        for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                _cache.append(json.loads(line))
    _loaded = True


def check(question: str, question_embedding: list[float]) -> dict | None:
    """
    Returns the matching cache entry (with at least "answer", "sources",
    "match_type", "similarity") if this question is an identical or
    near-identical repeat of one already answered, else None.
    """
    _ensure_loaded()
    normalized = _normalize(question)

    for entry in _cache:
        if entry["normalized_question"] == normalized:
            return {**entry, "match_type": "identical", "similarity": 1.0}

    best_entry = None
    best_score = 0.0
    for entry in _cache:
        score = _cosine(question_embedding, entry["embedding"])
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is not None and best_score >= SIMILARITY_THRESHOLD:
        return {**best_entry, "match_type": "near_identical", "similarity": round(best_score, 4)}

    return None


def store(question: str, question_embedding: list[float], answer: str,
          language: str, sources: list[str]) -> None:
    _ensure_loaded()
    entry = {
        "normalized_question": _normalize(question),
        "question": question,
        "embedding": question_embedding,
        "answer": answer,
        "language": language,
        "sources": sources,
    }
    _cache.append(entry)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
