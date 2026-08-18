"""
Task 5 -- Combines vector search (Task 3, via app/rag/retrieval.py) and
keyword search (keyword_search.py) into one ranked list using Reciprocal
Rank Fusion (RRF).

RRF is used instead of combining the two raw scores directly because
vector cosine similarity (roughly 0-1) and BM25 (unbounded, corpus-size
dependent) are not on comparable scales -- averaging or weighting them
directly would be arbitrary. RRF only looks at each chunk's *rank
position* within each list, so it needs no score normalization and no
tuning to combine the two fairly.
"""

RRF_K = 60  # standard RRF constant; large enough that rank 1 vs rank 2
            # matters less than "appearing near the top of both lists"


def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """
    rankings: one ranked list of chunk dicts per retrieval method (each
    already sorted best-first, each dict must have "chunk_id").

    A chunk's fused score is the sum, across every list it appears in, of
    1 / (k + rank). A chunk near the top of both lists scores higher than
    one that is #1 in only one list and absent from the other -- which is
    the point of fusing two independent signals rather than trusting
    either alone.
    """
    rrf_scores: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            cid = chunk["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
            # Keep the first (best-ranked) copy of each chunk's payload;
            # the text/metadata are identical everywhere it appears.
            chunk_by_id.setdefault(cid, chunk)

    fused = sorted(
        chunk_by_id.values(),
        key=lambda c: rrf_scores[c["chunk_id"]],
        reverse=True,
    )

    for chunk in fused:
        chunk["rrf_score"] = round(rrf_scores[chunk["chunk_id"]], 6)

    return fused
