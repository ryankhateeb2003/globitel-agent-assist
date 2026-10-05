"""
Manual, visual demo of exactly what retrieval_metrics.py does for ONE
question -- run this yourself in the terminal to see the comparison
happen with your own eyes, not just read about it.

Usage:
    docker exec -it globitel-app python -m eval.demo_single_question <dataset_id>
    docker exec -it globitel-app python -m eval.demo_single_question en-exact-001

Or with no id, it picks a random testable item from dataset_v1.json.
"""

import json
import random
import sys
from pathlib import Path

from app.retrieval.retrieval import search

K_VALUES = [1, 3, 5, 10]


def main():
    dataset = json.loads(Path("eval/task1_dataset/dataset_v1.json").read_text(encoding="utf-8"))

    if len(sys.argv) > 1:
        item = next((d for d in dataset if d["id"] == sys.argv[1]), None)
        if not item:
            print(f"No item with id '{sys.argv[1]}' found.")
            return
    else:
        testable = [d for d in dataset if d["type"] != "should_refuse"]
        item = random.choice(testable)

    correct_ids = [c.strip() for c in (item.get("_chunk_id") or "").split(",") if c.strip()]

    print("=" * 80)
    print(f"ID: {item['id']}  |  language: {item['language']}  |  type: {item['type']}")
    print(f"QUESTION: {item['question']}")
    print(f"KNOWN CORRECT ANSWER (from dataset_v1.json, built in Task 1):")
    print(f"  {item.get('expected_answer')}")
    print(f"KNOWN CORRECT chunk_id(s): {correct_ids}")
    print("=" * 80)

    print("\nRunning retrieval NOW (the system does NOT see the correct answer above)...\n")
    outcome = search(item["question"], mode="hybrid", top_k=10)
    results = outcome["results"]

    print(f"Retrieval took {outcome['elapsed_ms']} ms. Top 10 results:\n")
    first_hit_rank = None
    for rank, r in enumerate(results, start=1):
        is_correct = r["chunk_id"] in correct_ids
        if is_correct and first_hit_rank is None:
            first_hit_rank = rank
        marker = "  <== CORRECT ANSWER (matches what we already knew)" if is_correct else ""
        score = r.get("rerank_score", r.get("rrf_score", r.get("score")))
        print(f"  #{rank:2d}  score={score}  chunk_id={r['chunk_id']}{marker}")
        print(f"       {r['text'][:90]}")

    print("\n" + "=" * 80)
    print("SCORING (what retrieval_metrics.py computes from the above):")
    if first_hit_rank:
        print(f"  Correct answer found at rank #{first_hit_rank}")
        print(f"  MRR for this question = 1/{first_hit_rank} = {1/first_hit_rank:.3f}")
    else:
        print("  Correct answer NOT found in top 10 -> MRR = 0")
    for k in K_VALUES:
        hit = first_hit_rank is not None and first_hit_rank <= k
        print(f"  Hit@{k}: {'YES' if hit else 'no'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
