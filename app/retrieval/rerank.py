"""
Task 5 -- Reranking step: takes the fused (vector + keyword) candidate
list and re-scores each [query, chunk_text] pair with a cross-encoder,
which reads the query and the chunk together (unlike vector/keyword
search, which score them independently) and is therefore more accurate at
the cost of being far more expensive per candidate -- which is exactly
why it only runs over a small top-N shortlist, never the whole corpus.

Model: BAAI/bge-reranker-v2-m3 -- chosen for the same reason bge-m3 was
chosen for embeddings (Task 3): it is explicitly multilingual, from the
same team/family, so Arabic support is a design goal of the model, not an
incidental side effect.

Confirmed multilingual support empirically (not just from the model card):
predict()-ing an Arabic query against a matching Arabic passage scored
0.9412, and against an unrelated Arabic passage scored 0.0 -- a clean
separation that shows the model is actually reading Arabic semantics, not
just producing noise. See hybrid-results.md for the full test.
"""

from sentence_transformers import CrossEncoder

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_model: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)
    return _model


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    Re-scores every candidate against the query with the cross-encoder and
    returns them re-sorted best-first, each with a "rerank_score" field
    added. Candidates are expected to already be a short list (Task 5:
    "over the top 20") -- this is not meant to run over the full corpus.
    """
    if not candidates:
        return []

    model = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = round(float(score), 4)

    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
