"""
Part Two, Task 2 -- measures retrieval alone (not generation), against
eval/dataset_v1.json, using the real retrieval code from Part One
(app/retrieval/retrieval.py's search(), same function /ask calls).

Deliberately calls retrieval.py's search() directly, NOT the full /ask
pipeline -- main.py's query normalization step (an LLM call) sits in
front of retrieval and is a separate mitigation layer with its own cost;
measuring retrieval on the customer's raw wording first gives an honest
baseline of what the retrieval algorithm itself can do, before any
language-model help. (Task 4's experiments can test with normalization
on top of this baseline later if wanted.)

should_refuse items are excluded here -- they have no correct chunk to
measure hit-rate/MRR against by design (see eval/README.md); the correct
system behavior for them is refusal, which is what Task 6's guardrail
tests and Task 3's answer-quality checks measure, not retrieval ranking.

Usage: python eval/retrieval_metrics.py
"""

import json
from collections import defaultdict
from pathlib import Path

from app.retrieval.retrieval import search

K_VALUES = [1, 3, 5, 10]
MAX_K = max(K_VALUES)
MODE = "hybrid"  # matches /ask's default


def correct_chunk_ids(item: dict) -> list[str]:
    """multi_chunk items store two ids comma-separated (see
    build_dataset_part2.py); everything else has exactly one."""
    raw = item.get("_chunk_id")
    if not raw:
        return []
    return [c.strip() for c in raw.split(",")]


def score_item(item: dict) -> dict:
    correct = correct_chunk_ids(item)
    outcome = search(item["question"], mode=MODE, top_k=MAX_K)
    retrieved_ids = [r["chunk_id"] for r in outcome["results"]]

    # Rank (1-indexed) of the first correct chunk found, or None.
    first_hit_rank = None
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in correct:
            first_hit_rank = rank
            break

    per_k = {}
    for k in K_VALUES:
        top_k_ids = retrieved_ids[:k]
        found = [c for c in correct if c in top_k_ids]
        per_k[k] = {
            "hit": 1 if found else 0,
            "recall": len(found) / len(correct) if correct else 0,
            "precision": len(found) / k,
        }

    return {
        "id": item["id"],
        "language": item["language"],
        "type": item["type"],
        "correct_chunk_ids": correct,
        "retrieved_chunk_ids": retrieved_ids,
        "first_hit_rank": first_hit_rank,
        "mrr": (1 / first_hit_rank) if first_hit_rank else 0,
        "per_k": per_k,
        "elapsed_ms": outcome["elapsed_ms"],
    }


def aggregate(results: list[dict], group_key) -> dict:
    """group_key(item) -> group label, or None to skip grouping (one
    overall group)."""
    groups = defaultdict(list)
    for r in results:
        key = group_key(r) if group_key else "all"
        groups[key].append(r)

    summary = {}
    for key, items in groups.items():
        n = len(items)
        entry = {"n": n, "mrr": sum(r["mrr"] for r in items) / n}
        for k in K_VALUES:
            entry[f"hit@{k}"] = sum(r["per_k"][k]["hit"] for r in items) / n
            entry[f"recall@{k}"] = sum(r["per_k"][k]["recall"] for r in items) / n
            entry[f"precision@{k}"] = sum(r["per_k"][k]["precision"] for r in items) / n
        summary[key] = entry
    return summary


def run():
    dataset = json.loads(Path("eval/dataset_v1.json").read_text(encoding="utf-8"))
    testable = [item for item in dataset if item["type"] != "should_refuse"]
    print(f"Evaluating {len(testable)} items ({len(dataset) - len(testable)} should_refuse items excluded)")

    results = []
    for i, item in enumerate(testable, 1):
        r = score_item(item)
        results.append(r)
        print(f"[{i}/{len(testable)}] {item['id']} ({item['language']}/{item['type']}) "
              f"-> hit@5={r['per_k'][5]['hit']} mrr={r['mrr']:.3f}")

    return results


if __name__ == "__main__":
    results = run()

    by_language = aggregate(results, lambda r: r["language"])
    by_type_language = aggregate(results, lambda r: (r["language"], r["type"]))
    overall = aggregate(results, None)

    out = {
        "overall": overall["all"],
        "by_language": by_language,
        "by_type_language": {f"{k[1]}_{k[0]}": v for k, v in by_type_language.items()},
        "per_item": results,
    }
    Path("eval/retrieval_metrics_raw.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n[SAVED] eval/retrieval_metrics_raw.json")

    print("\n=== By language ===")
    for lang, m in by_language.items():
        print(f"{lang}: n={m['n']} MRR={m['mrr']:.3f} "
              + " ".join(f"hit@{k}={m[f'hit@{k}']:.2f}" for k in K_VALUES))
