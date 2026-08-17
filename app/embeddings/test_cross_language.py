"""
Task 3 deliverable: cross-language.md data.

Tests whether an Arabic query retrieves the English document holding the
same answer (and vice versa), using bge_m3 only -- minilm_en is already
established as unusable for Arabic, so cross-language behaviour on it is
not a meaningful product question.
"""

from app.embeddings.embed_store import get_model, collection_name, client


# Query in one language, but we know (from the corpus) that both an
# Arabic AND an English chunk exist with the same underlying answer.
CROSS_LANG_QUERIES = [
    {"query_lang": "ar", "query": "كيف بقدر افتح محفظة اورنج موني؟", "expects_topic": "orange-money"},
    {"query_lang": "en", "query": "How do I open an Orange Money wallet?", "expects_topic": "orange-money"},
    {"query_lang": "ar", "query": "شو هي رسوم استخدام الخدمة؟", "expects_topic": "orange-money"},
    {"query_lang": "en", "query": "What are the fees for using this service?", "expects_topic": "orange-money"},
]


def search_top5(query_text: str, top_k: int = 5) -> list[dict]:
    model = get_model("bge_m3")
    query_vector = model.encode(query_text, normalize_embeddings=True).tolist()

    results = client.query_points(
        collection_name=collection_name("bge_m3"),
        query=query_vector,
        limit=top_k,
    ).points

    return [
        {
            "score": round(r.score, 4),
            "language": r.payload["language"],
            "text_preview": r.payload["text"][:80].replace("\n", " "),
        }
        for r in results
    ]


def run_cross_language_test():
    for item in CROSS_LANG_QUERIES:
        print("\n" + "=" * 70)
        print(f"QUERY [{item['query_lang']}]: {item['query']}")
        print("=" * 70)

        results = search_top5(item["query"])

        other_lang_hits = [r for r in results if r["language"] != item["query_lang"]]

        for r in results:
            marker = "<-- CROSS-LANGUAGE" if r["language"] != item["query_lang"] else ""
            print(f"  score={r['score']}  lang={r['language']}  {marker}")
            print(f"    -> {r['text_preview']}...")

        print(f"\n  Cross-language hits in top-5: {len(other_lang_hits)}/5")


if __name__ == "__main__":
    run_cross_language_test()