"""
Task 4: retrieval helper that bridges Qdrant (Task 3) and the LLM answer
step. Takes a question, embeds it with the same model used to embed the
corpus (bge_m3 -- the model selected in Task 3), searches Qdrant, and
returns the retrieved chunks formatted as both a raw list (for the API
response's "retrieved_chunks" field) and a single context string ready
to drop into the prompt templates.
"""

from app.embeddings.embed_store import get_model, collection_name, client


def retrieve_chunks(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed the question with bge_m3 and return the top_k most similar
    chunks from Qdrant, each with its full payload (text, language,
    topic, source_file, etc.) plus the similarity score.
    """
    model = get_model("bge_m3")
    query_vector = model.encode(question, normalize_embeddings=True).tolist()

    name = collection_name("bge_m3")
    results = client.query_points(
        collection_name=name,
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