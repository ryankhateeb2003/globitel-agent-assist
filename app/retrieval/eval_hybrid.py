"""
Task 5 deliverable data generator: builds the 20-query test set (10 per
language, including exact-value queries -- fee, limit, or short code),
runs it through all 3 modes (vector / keyword / hybrid) via
app/retrieval/retrieval.py, and reports per-mode/per-language accuracy
and latency for hybrid-results.md.

Methodology mirrors app/embeddings/eval_retrieval.py (Task 3): questions
are sampled directly from chunks.jsonl's own FAQ question lines, so the
correct answer chunk is known in advance, not guessed.
"""

import random
import re

from app.retrieval.keyword_search import load_chunks
from app.retrieval.retrieval import search, vector_search, keyword_search, hybrid_search

random.seed(42)  # reproducible sample -- same 20 questions every run

EXACT_VALUE_PATTERN = re.compile(
    r"\*\d+#|دينار|JOD|\bfee\b|\bfees\b|رسوم|limit|الحد\b|حد\s"
)


def extract_question(chunk_text: str) -> str | None:
    first_line = chunk_text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def build_test_set(n_per_language: int = 10, n_exact_per_language: int = 3) -> list[dict]:
    """
    Per language: n_exact_per_language queries drawn from chunks whose
    text contains an exact value (short code / fee / limit), the rest
    drawn from the remaining pool -- 6 exact-value queries total across
    both languages, per Task 5's spec.
    """
    chunks = load_chunks("chunks.jsonl")

    candidates = {"en": [], "ar": []}
    for c in chunks:
        question = extract_question(c["text"])
        if question and len(question) > 8:
            candidates[c["language"]].append(
                {
                    "question": question,
                    "correct_chunk_id": c["chunk_id"],
                    "topic": c["topic"],
                    "has_exact_value": bool(EXACT_VALUE_PATTERN.search(c["text"])),
                }
            )

    test_set = []
    for lang in ["en", "ar"]:
        pool = candidates[lang]
        exact_pool = [c for c in pool if c["has_exact_value"]]
        other_pool = [c for c in pool if not c["has_exact_value"]]

        n_exact = min(n_exact_per_language, len(exact_pool))
        chosen_exact = random.sample(exact_pool, n_exact)

        n_other = min(n_per_language - n_exact, len(other_pool))
        chosen_other = random.sample(other_pool, n_other)

        for item in chosen_exact + chosen_other:
            item["language"] = lang
        test_set.extend(chosen_exact)
        test_set.extend(chosen_other)

    return test_set


def warm_up():
    """
    Loads every model used by any mode once, outside of any timed section,
    so the reported per-query latencies reflect a warm server (Task 4's
    /ask process, which loads models once at startup) instead of being
    dominated by one-time model-load cost on the first query of each mode.
    """
    vector_search("warm up", top_k=1)
    keyword_search("warm up", top_k=1)
    hybrid_search("warm up", top_k=1)


def run_evaluation(top_k: int = 5):
    warm_up()

    test_set = build_test_set()
    modes = ["vector", "keyword", "hybrid"]

    results = {mode: {"en": [], "ar": []} for mode in modes}

    for item in test_set:
        lang = item["language"]
        for mode in modes:
            outcome = search(item["question"], mode=mode, top_k=top_k)
            returned_ids = [r["chunk_id"] for r in outcome["results"]]

            results[mode][lang].append(
                {
                    "question": item["question"],
                    "topic": item["topic"],
                    "has_exact_value": item["has_exact_value"],
                    "correct_chunk_id": item["correct_chunk_id"],
                    "top1_correct": bool(returned_ids) and returned_ids[0] == item["correct_chunk_id"],
                    "top5_correct": item["correct_chunk_id"] in returned_ids,
                    "elapsed_ms": outcome["elapsed_ms"],
                    "top1_chunk_id": returned_ids[0] if returned_ids else None,
                    "top1_preview": outcome["results"][0]["text"][:100].replace("\n", " ") if outcome["results"] else "",
                }
            )

            print(
                f"[{mode:7s}][{lang}] top1={'OK ' if results[mode][lang][-1]['top1_correct'] else 'MISS'} "
                f"({outcome['elapsed_ms']:>8.2f} ms) {item['question'][:60]}"
            )

    return results, test_set


def summarize(results: dict) -> None:
    print("\n" + "#" * 70)
    print("SUMMARY")
    print("#" * 70)
    for mode, by_lang in results.items():
        for lang, items in by_lang.items():
            top1 = sum(1 for i in items if i["top1_correct"])
            top5 = sum(1 for i in items if i["top5_correct"])
            avg_ms = sum(i["elapsed_ms"] for i in items) / len(items) if items else 0
            print(
                f"{mode:7s} | {lang} | top1={top1}/{len(items)} | "
                f"top5={top5}/{len(items)} | avg_latency={avg_ms:.2f} ms"
            )


if __name__ == "__main__":
    results, test_set = run_evaluation()
    summarize(results)

    import json
    with open("app/retrieval/eval_results_raw.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n[SAVED] app/retrieval/eval_results_raw.json")
