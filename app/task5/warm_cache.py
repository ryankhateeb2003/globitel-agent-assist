"""
Task 5: cache warm-up -- sends every answerable question in
eval/task1_dataset/dataset_v1.json through the real, live /ask endpoint
once, so each one's answer gets stored by app/task5/cache.py (see
stream.py's answer_response()).

Naturally resumable with zero extra logic: a question already cached
returns a cache hit immediately (cache_hit=True in the response, no
Groq call made), so re-running this script after a quota stop just
skips everything already warmed and continues from where it left off.

should_refuse items are skipped -- they never reach the "store a real
answer" path (refusals aren't cached, see stream.py's cached_response()
vs guardrail_response()), so sending them here would just burn a Groq
call for nothing to show for it.

Usage (from inside the app container, server must be running):
    python -m app.task5.warm_cache
"""

import json
import time
from pathlib import Path

import requests

DATASET_PATH = Path("eval/task1_dataset/dataset_v1.json")
ASK_URL = "http://localhost:8000/ask"


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    questions = [d for d in dataset if d["type"] != "should_refuse"]

    warmed = 0
    already_cached = 0
    failed = 0

    for i, item in enumerate(questions, 1):
        start = time.perf_counter()
        try:
            resp = requests.post(ASK_URL, json={"question": item["question"]}, timeout=120)
            resp.raise_for_status()
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(questions)}] {item['id']} FAILED: {type(e).__name__} {e}", flush=True)
            if "RateLimitError" in str(e) or "429" in str(e):
                print("Looks like a rate limit -- stopping here, safe to re-run later.")
                break
            continue

        text = resp.text
        cache_hit = '"cache_hit": true' in text
        elapsed_ms = (time.perf_counter() - start) * 1000

        if cache_hit:
            already_cached += 1
            print(f"[{i}/{len(questions)}] {item['id']} already cached ({elapsed_ms:.0f}ms)", flush=True)
        else:
            warmed += 1
            print(f"[{i}/{len(questions)}] {item['id']} warmed ({elapsed_ms:.0f}ms)", flush=True)

    print(f"\nDone this run -- newly warmed: {warmed}, already cached: {already_cached}, failed: {failed}")


if __name__ == "__main__":
    main()
