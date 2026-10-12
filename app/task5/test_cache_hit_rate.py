"""
Task 5 deliverable: "Cache hit rate over 200 queries".

Builds a simulated 200-question traffic stream from this project's own
eval set (app/task5/warm_cache.py should be run first so the cache is
pre-populated, matching how a real deployment would start the day with
its common questions already warm):

- ~85% repeated draws from the cached (answerable, "known FAQ") pool,
  weighted so a few questions are asked far more often than others --
  per the task brief's own framing ("a contact center has a very
  repetitive question distribution"), not a uniform random pick.
- ~15% draws from the should_refuse questions (genuinely out-of-scope
  topics, e.g. weather, unrelated small talk) -- these are never cached
  by design (see cache.py / stream.py's guardrail_response path), so
  they are expected, legitimate misses. Included so the measured hit
  rate reflects a realistic mixed traffic pattern instead of an
  artificially perfect 100% that would only happen if every question
  were guaranteed to already be in the cache.

Sends each question through the real /ask endpoint (so this exercises
the actual cache.py check(), not a simulation of it) and tallies
hit vs miss, split by match_type (identical / near_identical / miss).

Usage (server must already be running, cache should be pre-warmed):
    python -m app.task5.test_cache_hit_rate
"""

import json
import random
import time
from collections import Counter
from pathlib import Path

import requests

DATASET_PATH = Path("eval/task1_dataset/dataset_v1.json")
CACHE_PATH = Path("cache/qa_cache.jsonl")
ASK_URL = "http://localhost:8000/ask"
OUT_PATH = Path("eval/task5_optimisation/results/cache_hit_rate_200.json")

N_QUERIES = 200
REFUSE_FRACTION = 0.15  # ~15% out-of-scope traffic mixed in
random.seed(42)  # reproducible sample


def build_traffic() -> list[dict]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cached_questions = {json.loads(l)["question"] for l in CACHE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()}

    known_pool = [d for d in dataset if d["question"] in cached_questions]
    refuse_pool = [d for d in dataset if d["type"] == "should_refuse"]

    n_refuse = round(N_QUERIES * REFUSE_FRACTION)
    n_known = N_QUERIES - n_refuse

    # Zipf-like weights so a handful of questions dominate traffic,
    # matching "very repetitive" real contact-center distribution
    # instead of a flat uniform pick.
    weights = [1 / (i + 1) for i in range(len(known_pool))]
    shuffled_pool = known_pool.copy()
    random.shuffle(shuffled_pool)

    traffic = random.choices(shuffled_pool, weights=weights, k=n_known)
    traffic += random.choices(refuse_pool, k=n_refuse)
    random.shuffle(traffic)
    return traffic


def main() -> None:
    traffic = build_traffic()
    print(f"Built {len(traffic)}-question traffic stream "
          f"({sum(1 for t in traffic if t['type'] != 'should_refuse')} known-pool draws, "
          f"{sum(1 for t in traffic if t['type'] == 'should_refuse')} out-of-scope draws)")

    records = []
    if OUT_PATH.exists():
        records = json.loads(OUT_PATH.read_text(encoding="utf-8"))["items"]
    done = len(records)

    def save() -> None:
        hits = sum(1 for r in records if r["cache_hit"])
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps({
            "n": len(records),
            "hits": hits,
            "hit_rate": round(hits / len(records), 4) if records else None,
            "match_types": dict(Counter(r["match_type"] for r in records if r["cache_hit"])),
            "items": records,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    for i, item in enumerate(traffic, 1):
        if i <= done:
            continue
        start = time.perf_counter()
        try:
            resp = requests.post(ASK_URL, json={"question": item["question"]}, timeout=120)
            total_ms = (time.perf_counter() - start) * 1000
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[{i}/{len(traffic)}] request failed: {type(e).__name__} {e}")
            print("Likely a rate limit -- stopping here, safe to re-run later.")
            break

        _, _, meta_part = resp.text.partition("\n\n---METADATA---\n")
        meta = json.loads(meta_part) if meta_part else {}

        record = {
            "id": item["id"], "type": item["type"],
            "cache_hit": meta.get("cache_hit", False),
            "match_type": meta.get("cache_match_type"),
            "total_ms": total_ms,
        }
        records.append(record)
        save()
        tag = "HIT " + (record["match_type"] or "") if record["cache_hit"] else "MISS"
        print(f"[{i}/{len(traffic)}] {item['id']} {tag} ({total_ms:.0f}ms)", flush=True)

    hits = sum(1 for r in records if r["cache_hit"])
    print(f"\n[SAVED] {OUT_PATH} -- {len(records)}/{len(traffic)} done, "
          f"hit rate so far: {hits}/{len(records)} = {hits/len(records)*100:.1f}%")


if __name__ == "__main__":
    main()
