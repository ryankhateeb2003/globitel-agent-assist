"""
Task 4: retrieval helper that bridges Qdrant (Task 3) and the LLM answer
step. Takes a question, embeds it, searches Qdrant, and returns the
retrieved chunks formatted as both a raw list (for the API response's
"retrieved_chunks" field) and a single context string ready to drop into
the prompt templates.

Embedding backend switch (added for the globitelai-bge A/B test): set the
EMBEDDING_BACKEND environment variable to choose which model/collection
is used --
  "bge_m3"               -- local BAAI/bge-m3, collection "chunks_bge_m3"
  "globitelai_bge" (default) -- Globitel's own hosted embedding API
                              (app/embeddings/globitel_bge.py), collection
                              "chunks_globitelai_bge"
Both collections hold vectors for the SAME chunks.jsonl, so switching is
safe -- production's "chunks_bge_m3" collection is never modified by
this, only which one gets queried.
"""

import os

from app.embeddings.embed_store import get_model, collection_name, client

# Default backend when a caller doesn't specify one explicitly (the UI
# no longer sends one, so this is what /ask uses too). Globitel's hosted
# model is the production choice; the local BGE-M3 is only loaded if a
# caller explicitly asks for "bge_m3".
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "globitelai_bge")


def _embed_query(question: str, embedding_backend: str) -> list[float]:
    if embedding_backend == "globitelai_bge":
        from app.embeddings.globitel_bge import embed_texts, get_api_key
        return embed_texts([question], get_api_key())[0].tolist()

    model = get_model("bge_m3")
    return model.encode(question, normalize_embeddings=True).tolist()


def _active_collection_name(embedding_backend: str) -> str:
    if embedding_backend == "globitelai_bge":
        return "chunks_globitelai_bge"
    return collection_name("bge_m3")


def retrieve_chunks(question: str, top_k: int = 5, embedding_backend: str | None = None) -> list[dict]:
    """
    Embed the question with `embedding_backend` ("bge_m3" or
    "globitelai_bge"; defaults to the EMBEDDING_BACKEND env var if not
    given) and return the top_k most similar chunks from the matching
    Qdrant collection, each with its full payload (text, language, topic,
    source_file, etc.) plus the similarity score.
    """
    embedding_backend = embedding_backend or EMBEDDING_BACKEND
    query_vector = _embed_query(question, embedding_backend)

    results = client.query_points(
        collection_name=_active_collection_name(embedding_backend),
        query=query_vector,
        limit=top_k,
    ).points

    return [
        {
            "chunk_id": r.payload["chunk_id"],
            "text": r.payload["text"],
            "language": r.payload["language"],
            "topic": r.payload["topic"],
            "source_file": r.payload["source_file"],
            "score": round(r.score, 4),
        }
        for r in results
    ]


def build_context(chunks: list[dict]) -> str:
    """
    Join retrieved chunks into a single context string for the prompt.
    Each chunk is labeled with its source so the answer can be traced
    back to a specific document (needed for the "sources" field in the
    /ask response).
    """
    if not chunks:
        return ""

    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Source {i}: {c['source_file']}]\n{c['text']}")

    return "\n\n".join(parts)


if __name__ == "__main__":
    test_question = "كيف بقدر افتح محفظة اورنج موني؟"
    chunks = retrieve_chunks(test_question, top_k=3)

    print(f"Question: {test_question}\n")
    for c in chunks:
        print(f"score={c['score']}  lang={c['language']}  source={c['source_file']}")
        print(f"  {c['text'][:100]}...\n")

    print("--- Built context ---")
    print(build_context(chunks))