"""
Task 3 deliverable: embedding-comparison.md data.

Randomly samples 10 English + 10 Arabic FAQ questions directly from
chunks.jsonl (i.e. real questions with a known, verifiable correct
answer -- the chunk they came from), runs each as a search query against
both models, and reports whether each model's #1 result is the correct
chunk.
"""

import random
import re

from app.embeddings.embed_store import get_model, collection_name, client, load_chunks


random.seed(42)  # reproducible sample -- same 20 questions every run


def extract_question(chunk_text: str) -> str | None:
    """
    Structure-based chunks start with a question line (per chunker.py's
    logic: ends with '?' or '؟'). Pull just that first line to use as the
    search query -- this mimics a real agent typing a short question, not
    pasting the whole FAQ answer back in as the query.
    """
    first_line = chunk_text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def build_test_set(n_per_language: int = 10) -> list[dict]:
    records = load_chunks("chunks.jsonl")

    candidates = {"en": [], "ar": []}
    for r in records:
        question = extract_question(r["text"])
        if question and len(question) > 8:  # skip trivially short/noisy lines
            candidates[r["language"]].append(
                {
                    "question": question,
                    "correct_chunk_id": r["chunk_id"],
                    "correct_topic": r["topic"],
                }
            )

    test_set = []
    for lang in ["en", "ar"]:
        pool = candidates[lang]
        sample_size = min(n_per_language, len(pool))
        test_set.extend(random.sample(pool, sample_size))

    return test_set


def search_top1(model_key: str, query_text: str) -> dict:
    model = get_model(model_key)
    query_vector = model.encode(query_text, normalize_embeddings=True).tolist()

    name = collection_name(model_key)
    results = client.query_points(
        collection_name=name,
        query=query_vector,
        limit=1,
    ).points

    top = results[0]
    return {
        "chunk_id": top.payload["chunk_id"],
        "score": round(top.score, 4),
        "text_preview": top.payload["text"][:100].replace("\n", " "),
    }


def run_evaluation():
    test_set = build_test_set(n_per_language=10)

    results_summary = {"minilm_en": {"correct": 0, "total": 0}, "bge_m3": {"correct": 0, "total": 0}}

    for i, item in enumerate(test_set, 1):
        print("\n" + "=" * 70)
        print(f"[{i}] QUESTION: {item['question']}")
        print(f"    EXPECTED chunk_id: {item['correct_chunk_id']} (topic: {item['correct_topic']})")
        print("=" * 70)

        for model_key in ["minilm_en", "bge_m3"]:
            top = search_top1(model_key, item["question"])
            is_correct = top["chunk_id"] == item["correct_chunk_id"]

            results_summary[model_key]["total"] += 1
            if is_correct:
                results_summary[model_key]["correct"] += 1

            status = "CORRECT" if is_correct else "WRONG"
            print(f"  {model_key:12s} [{status:7s}] score={top['score']}  -> {top['text_preview']}...")

    print("\n" + "#" * 70)
    print("FINAL ACCURACY (top-1 correct chunk retrieved)")
    print("#" * 70)
    for model_key, stats in results_summary.items():
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {model_key:12s}: {stats['correct']}/{stats['total']} = {acc:.1f}%")


if __name__ == "__main__":
    run_evaluation()