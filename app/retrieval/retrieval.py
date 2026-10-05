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


def vector_search(query: str, top_k: int = 5, embedding_backend: str | None = None) -> list[dict]:
    """Thin wrapper so this module exposes the same *_search(query, top_k)
    shape for all three modes -- keeps eval_hybrid.py's comparison loop
    uniform instead of special-casing the vector path."""
    return _vector_retrieve_chunks(query, top_k=top_k, embedding_backend=embedding_backend)


def keyword_search(query: str, top_k: int = 5) -> list[dict]:
    return _keyword_search(query, top_k=top_k)


def hybrid_search(
    query: str, top_k: int = 5, rerank_candidates: int = RERANK_CANDIDATES,
    use_rerank: bool = False, embedding_backend: str | None = None,
) -> list[dict]:
    """
    Vector + keyword, fused with RRF, truncated to top_k.

    Each of the two underlying searches is run over `rerank_candidates`
    (20) results, not just `top_k`, so fusion has enough material to
    actually re-order -- asking each side for only the final top_k first
    would throw away exactly the chunks a weaker-but-correct signal from
    the *other* method might have promoted.

    `use_rerank` defaults to False: manual live testing (see
    hybrid-results.md's "Known limitation" section and the /ask session
    log) found bge-reranker-v2-m3 demoting an already-correct top-1
    result often enough -- including one case where it dragged a
    genuinely correct chunk's score so low the relevance-threshold check
    refused to answer a question it actually had the right information
    for -- that it was no longer a net win over plain RRF fusion, while
    being 5-10x slower (reranking is the dominant cost in every hybrid
    latency measurement recorded in hybrid-results.md). The reranker
    itself (rerank.py) is NOT deleted -- Task 5's deliverable requires
    the 3-way comparison to stay reproducible, so `use_rerank=True` still
    runs the original reranked path for that purpose.
    """
    return _hybrid_search_detailed(
        query, top_k=top_k, rerank_candidates=rerank_candidates,
        use_rerank=use_rerank, embedding_backend=embedding_backend,
    )["results"]


def _hybrid_search_detailed(
    query: str, top_k: int = 5, rerank_candidates: int = RERANK_CANDIDATES,
    use_rerank: bool = False, embedding_backend: str | None = None,
) -> dict:
    """
    hybrid_search() plus what /ask needs on the side: the plain vector
    half's top cosine score (the guardrail's confidence signal -- RRF's
    own score is rank-based and useless for that, see guardrails.py) and
    per-half timings. Reusing the vector half's score here saves /ask a
    second embedding call + Qdrant query for the same question.
    """
    t0 = time.perf_counter()
    vector_results = vector_search(query, top_k=rerank_candidates, embedding_backend=embedding_backend)
    t1 = time.perf_counter()
    keyword_results = keyword_search(query, top_k=rerank_candidates)
    t2 = time.perf_counter()

    # Raw cosine of the best vector match -- read before fusion re-sorts
    # the chunks by rrf_score.
    vector_top_score = vector_results[0]["score"] if vector_results else None
    fused = reciprocal_rank_fusion([vector_results, keyword_results])

    results = rerank(query, fused[:rerank_candidates])[:top_k] if use_rerank else fused[:top_k]

    return {
        "results": results,
        "vector_top_score": vector_top_score,
        "vector_ms": round((t1 - t0) * 1000, 2),
        "keyword_ms": round((t2 - t1) * 1000, 2),
    }


def search(query: str, mode: str = "hybrid", top_k: int = 5, embedding_backend: str | None = None) -> list[dict]:
    """
    Single entry point for all three modes, with per-call latency attached
    (used directly by eval_hybrid.py's latency table -- Task 5 requires
    latency to be measured per mode per language, and reranking is not
    free, so it needs to be visible here, not just in vector/keyword).

    `embedding_backend` ("bge_m3" or "globitelai_bge") only affects the
    vector half of retrieval -- passed through so /ask can let a customer
    pick the embedding model per-request instead of only at server
    startup (see app/rag/retrieval.py's EMBEDDING_BACKEND).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown retrieval mode '{mode}'. Choose from: {sorted(VALID_MODES)}")

    start = time.perf_counter()

    extra = {}
    if mode == "vector":
        results = vector_search(query, top_k=top_k, embedding_backend=embedding_backend)
    elif mode == "keyword":
        results = keyword_search(query, top_k=top_k)
    else:
        detailed = _hybrid_search_detailed(query, top_k=top_k, embedding_backend=embedding_backend)
        results = detailed.pop("results")
        extra = detailed

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return {"mode": mode, "query": query, "elapsed_ms": elapsed_ms, "results": results, **extra}


if __name__ == "__main__":
    test_question = "شو الكود اللي بتصل عليه احدد حد تجوال البيانات؟"

    for mode in ["vector", "keyword", "hybrid"]:
        outcome = search(test_question, mode=mode, top_k=3)
        print(f"\n=== mode={mode} ({outcome['elapsed_ms']} ms) ===")
        for r in outcome["results"]:
            print(f"  [{r.get('rrf_score', r.get('score'))}] {r['chunk_id']} | {r['text'][:70]}...")
