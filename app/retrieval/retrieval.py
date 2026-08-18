"""
Task 5 -- Unified retrieval interface: vector, keyword, and hybrid
(vector + keyword, fused with RRF, reranked) behind one function.

This is the file the Task 5 deliverable list names directly. It wires
together three previously-separate pieces so hybrid-results.md can compare
them fairly under one interface:
  - vector search  -> app/rag/retrieval.py (Task 4's BGE-M3 / Qdrant helper)
  - keyword search  -> keyword_search.py (this package, Task 5)
  - fusion          -> hybrid.py (this package, Task 5)
  - reranking       -> rerank.py (this package, Task 5)
"""

import time

from app.rag.retrieval import retrieve_chunks as _vector_retrieve_chunks
from app.retrieval.keyword_search import keyword_search as _keyword_search
from app.retrieval.hybrid import reciprocal_rank_fusion
from app.retrieval.rerank import rerank

# Reranking runs over this many fused candidates and keeps the best
# RERANK_KEEP -- per Task 5's spec ("over the top 20, keeping the best 5").
RERANK_CANDIDATES = 20
RERANK_KEEP = 5

VALID_MODES = {"vector", "keyword", "hybrid"}


def vector_search(query: str, top_k: int = 5) -> list[dict]:
    """Thin wrapper so this module exposes the same *_search(query, top_k)
    shape for all three modes -- keeps eval_hybrid.py's comparison loop
    uniform instead of special-casing the vector path."""
    return _vector_retrieve_chunks(query, top_k=top_k)


def keyword_search(query: str, top_k: int = 5) -> list[dict]:
    return _keyword_search(query, top_k=top_k)


def hybrid_search(query: str, top_k: int = 5, rerank_candidates: int = RERANK_CANDIDATES) -> list[dict]:
    """
    Vector + keyword, fused with RRF, reranked, truncated to top_k.

    Each of the two underlying searches is run over `rerank_candidates`
    (20) results, not just `top_k`, so fusion and reranking have enough
    material to actually re-order -- asking each side for only the final
    top_k first would throw away exactly the chunks a weaker-but-correct
    signal from the *other* method might have promoted.
    """
    vector_results = vector_search(query, top_k=rerank_candidates)
    keyword_results = keyword_search(query, top_k=rerank_candidates)

    fused = reciprocal_rank_fusion([vector_results, keyword_results])
    reranked = rerank(query, fused[:rerank_candidates])

    return reranked[:top_k]


def search(query: str, mode: str = "hybrid", top_k: int = 5) -> list[dict]:
    """
    Single entry point for all three modes, with per-call latency attached
    (used directly by eval_hybrid.py's latency table -- Task 5 requires
    latency to be measured per mode per language, and reranking is not
    free, so it needs to be visible here, not just in vector/keyword).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown retrieval mode '{mode}'. Choose from: {sorted(VALID_MODES)}")

    start = time.perf_counter()

    if mode == "vector":
        results = vector_search(query, top_k=top_k)
    elif mode == "keyword":
        results = keyword_search(query, top_k=top_k)
    else:
        results = hybrid_search(query, top_k=top_k)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return {"mode": mode, "query": query, "elapsed_ms": elapsed_ms, "results": results}


if __name__ == "__main__":
    test_question = "شو الكود اللي بتصل عليه احدد حد تجوال البيانات؟"

    for mode in ["vector", "keyword", "hybrid"]:
        outcome = search(test_question, mode=mode, top_k=3)
        print(f"\n=== mode={mode} ({outcome['elapsed_ms']} ms) ===")
        for r in outcome["results"]:
            print(f"  [{r.get('rrf_score', r.get('score'))}] {r['chunk_id']} | {r['text'][:70]}...")
