"""
Task 5: "After" measurement.

Sends the exact same question ids that completed in "Before"
(eval/task4_experiments/results/task5_before.json) through the REAL
live /ask endpoint -- not Groq directly like run_experiment.py -- so
app/task5/cache.py and model_router.py (both only wired into the live
server) actually run. Hit@5 and Faithfulness are scored the same way
run_experiment.py does (same retrieval_scores() + Task 3 judge), reused
directly so the numbers are comparable to "Before".

Resumable like run_experiment.py: already-recorded ids are skipped on
re-run, so a quota stop partway through is safe.

Usage (from inside the app container, server must already be running):
    python -m app.task5.measure_after
"""

import json
import os
import time
from pathlib import Path

import requests
from groq import Groq

from eval.task4_experiments.run_experiment import retrieval_scores
from eval.task3_answer_quality.answer_quality import run_judge

ASK_URL = "http://localhost:8000/ask"
DATASET_PATH = Path("eval/task1_dataset/dataset_v1.json")
PRODUCTION_CHUNKS = Path("chunks.jsonl")  # gold answer text source -- same file run_experiment.py reads from, independent of which chunk set retrieval actually used
BEFORE_PATH = Path("eval/task5_optimisation/results/before.json")
OUT_PATH = Path("eval/task5_optimisation/results/after.json")


def load_gold() -> dict:
    gold_by_id = {}
    with PRODUCTION_CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            gold_by_id[c["chunk_id"]] = c["text"]
    return gold_by_id


def main() -> None:
    before = json.loads(BEFORE_PATH.read_text(encoding="utf-8"))
    before_ids = [it["id"] for it in before["items"]]

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in dataset}
    gold_by_id = load_gold()

    groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

    records = []
    if OUT_PATH.exists():
        records = json.loads(OUT_PATH.read_text(encoding="utf-8"))["items"]
    done = {r["id"] for r in records}

    def save() -> None:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps({"items": records}, ensure_ascii=False, indent=2), encoding="utf-8")

    for i, qid in enumerate(before_ids, 1):
        if qid in done:
            continue
        item = by_id[qid]
        start = time.perf_counter()
        try:
            resp = requests.post(ASK_URL, json={"question": item["question"]}, timeout=120)
            total_ms = (time.perf_counter() - start) * 1000
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Most likely the server's own Groq call hit a 429 mid-stream,
            # which breaks the response connection from here rather than
            # a clean HTTP error status -- same quota-stop situation
            # run_experiment.py handles, just surfaced differently since
            # this goes through a real streaming HTTP response instead of
            # a direct SDK call. Safe to stop; already-saved items are
            # untouched and re-running resumes from here.
            print(f"[{i}/{len(before_ids)}] {item['id']} request failed: {type(e).__name__} {e}")
            print("Likely a rate limit mid-stream -- stopping here, safe to re-run later.")
            break

        text = resp.text
        answer_part, _, meta_part = text.partition("\n\n---METADATA---\n")
        meta = json.loads(meta_part)

        retrieved = meta.get("retrieved_chunks") or []
        ranking = [{"chunk_id": c["chunk_id"], "text": c.get("text", "")} for c in retrieved]
        gold_texts = [gold_by_id[cid] for cid in item.get("_chunk_id", "").split(",") if cid in gold_by_id]
        scores = retrieval_scores(gold_texts, ranking) if gold_texts else {}

        faithfulness = None
        if retrieved and answer_part.strip():
            context = "\n\n".join(c.get("text", "") for c in retrieved)
            judged = run_judge(groq_client, "faithfulness", context=context,
                                question=item["question"], answer=answer_part.strip())
            faithfulness = judged["score"]

        record = {
            "id": item["id"], "language": item["language"], "type": item["type"],
            "total_ms": total_ms,
            "cache_hit": meta.get("cache_hit", False),
            "cache_match_type": meta.get("cache_match_type"),
            "generation_model": meta.get("generation_model"),
            "token_usage": meta.get("token_usage"),
            "faithfulness": faithfulness,
            **scores,
        }
        records.append(record)
        save()
        print(f"[{i}/{len(before_ids)}] {item['id']} total={total_ms:.0f}ms "
              f"cache={record['cache_hit']} model={record['generation_model']} "
              f"faith={faithfulness}", flush=True)

    print(f"\n[SAVED] {OUT_PATH} -- {len(records)}/{len(before_ids)} done")


if __name__ == "__main__":
    main()
