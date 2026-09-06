"""
Part Two, Task 2 (follow-up comparison) -- same measurement as
retrieval_metrics.py, but with main.py's query-normalization step
(normalize_query_for_retrieval, one Groq call) applied before retrieval.
Answers directly: does normalization change the retrieval numbers, and
by how much, per language and per type?

Usage: python eval/retrieval_metrics_normalized.py
"""

import json
import os
from collections import defaultdict
from pathlib import Path

from groq import Groq

from app.retrieval.retrieval import search
from app.guardrails.guardrails import normalize_query_for_retrieval

GROQ_MODEL = "qwen/qwen3.6-27b"
K_VALUES = [1, 3, 5, 10]
MAX_K = max(K_VALUES)
MODE = "hybrid"


def correct_chunk_ids(item: dict) -> list[str]:
    raw = item.get("_chunk_id")
    if not raw:
        return []
    return [c.strip() for c in raw.split(",")]


def score_item(item: dict, client) -> dict:
    correct = correct_chunk_ids(item)
    normalized_q = normalize_query_for_retrieval(client, GROQ_MODEL, item["question"], item["language"])
    outcome = search(normalized_q, mode=MODE, top_k=MAX_K)
    retrieved_ids = [r["chunk_id"] for r in outcome["results"]]

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
        "id": item["id"], "language": item["language"], "type": item["type"],
        "original_question": item["question"], "normalized_question": normalized_q,
        "correct_chunk_ids": correct, "retrieved_chunk_ids": retrieved_ids,
        "first_hit_rank": first_hit_rank,
        "mrr": (1 / first_hit_rank) if first_hit_rank else 0,
        "per_k": per_k,
    }


def aggregate(results: list[dict], group_key) -> dict:
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
        summary[key] = entry
    return summary


def run():
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    dataset = json.loads(Path("eval/dataset_v1.json").read_text(encoding="utf-8"))
    testable = [item for item in dataset if item["type"] != "should_refuse"]
    print(f"Evaluating {len(testable)} items WITH query normalization")

    results = []
    for i, item in enumerate(testable, 1):
        r = score_item(item, client)
        results.append(r)
        changed = "" if r["original_question"] == r["normalized_question"] else " [rewritten]"
        print(f"[{i}/{len(testable)}] {item['id']} -> hit@5={r['per_k'][5]['hit']} mrr={r['mrr']:.3f}{changed}")

    return results


if __name__ == "__main__":
    results = run()
    by_language = aggregate(results, lambda r: r["language"])
    by_type_language = aggregate(results, lambda r: f"{r['type']}_{r['language']}")

    out = {"by_language": by_language, "by_type_language": by_type_language, "per_item": results}
    Path("eval/retrieval_metrics_normalized_raw.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n[SAVED] eval/retrieval_metrics_normalized_raw.json")
    print("\n=== By language (WITH normalization) ===")
    for lang, m in by_language.items():
        print(f"{lang}: n={m['n']} MRR={m['mrr']:.3f} "
              + " ".join(f"hit@{k}={m[f'hit@{k}']:.2f}" for k in K_VALUES))
