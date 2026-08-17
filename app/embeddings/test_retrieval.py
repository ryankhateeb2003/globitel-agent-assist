"""
Task 3 requirement: compare retrieval quality of the English-only model
(minilm_en) against the multilingual model (bge_m3) on the same queries,
in both English and Arabic.

This produces the numbers behind embedding-comparison.md's claim that an
English-only embedding model is not usable for this product.
"""

from app.embeddings.embed_store import get_model, collection_name, client


# A handful of representative test queries. Real deliverable wants 10 per
# language -- start small here to sanity-check the mechanism works, then
# scale up once we confirm the output looks right.
TEST_QUERIES = [
    {"lang": "en", "text": "How do I open an Orange Money wallet?"},
    {"lang": "ar", "text": "كيف بقدر افتح محفظة اورنج موني؟"},
    {"lang": "en", "text": "What is the emergency credit service?"},
    {"lang": "ar", "text": "شو هو رصيد الطوارئ؟"},
]


def search(model_key: str, query_text: str, top_k: int = 3) -> list[dict]:
    model = get_model(model_key)
    query_vector = model.encode(query_text, normalize_embeddings=True).tolist()

    name = collection_name(model_key)
    results = client.query_points(
        collection_name=name,
        query=query_vector,
        limit=top_k,
    ).points

    return [
        {
            "score": round(r.score, 4),
            "language": r.payload["language"],
            "topic": r.payload["topic"],
            "text_preview": r.payload["text"][:120].replace("\n", " "),
        }
        for r in results
    ]


def run_comparison():
    for query in TEST_QUERIES:
        print("\n" + "=" * 70)
        print(f"QUERY [{query['lang']}]: {query['text']}")
        print("=" * 70)

        for model_key in ["minilm_en", "bge_m3"]:
            print(f"\n--- {model_key} ---")
            results = search(model_key, query["text"])
            for r in results:
                print(f"  score={r['score']}  lang={r['language']}  topic={r['topic']}")
                print(f"    -> {r['text_preview']}...")


if __name__ == "__main__":
    run_comparison()