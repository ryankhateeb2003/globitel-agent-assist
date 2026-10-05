"""
Part Two, Task 3 (step 1) -- generates the REAL answers the system
actually gives, for every item in dataset_v1.json (all 80, including
should_refuse -- we need to see what the system actually said for those
too, to confirm it refused rather than answered).

Calls the live /ask endpoint over HTTP (not retrieval.py directly, unlike
Task 2) -- Task 3 judges the full production pipeline's output: guardrail
decision + generation, not retrieval alone. Requires the app container to
be running and reachable (docker exec -d globitel-app uvicorn ...).

/ask streams plain text, then a "---METADATA---" marker, then a JSON
blob (see app/api/main.py) -- this script requests it as one blocking
call and splits the two parts itself.

Usage: python eval/generate_answers.py
"""

import json
import time
from pathlib import Path

import requests

ASK_URL = "http://localhost:8000/ask"
METADATA_MARKER = "\n\n---METADATA---\n"


def call_ask(question: str) -> dict:
    resp = requests.post(ASK_URL, json={"question": question, "mode": "hybrid"}, timeout=120)
    resp.raise_for_status()
    body = resp.text
    if METADATA_MARKER in body:
        answer_text, meta_json = body.split(METADATA_MARKER, 1)
        metadata = json.loads(meta_json)
    else:
        # Defensive: if the marker is ever missing, keep the raw body
        # rather than crashing the whole run.
        answer_text, metadata = body, {}
    return {"answer_text": answer_text.strip(), "metadata": metadata}


def run():
    dataset = json.loads(Path("eval/task1_dataset/dataset_v1.json").read_text(encoding="utf-8"))
    print(f"Generating real answers for {len(dataset)} items via {ASK_URL} ...")

    results = []
    for i, item in enumerate(dataset, 1):
        t0 = time.time()
        try:
            outcome = call_ask(item["question"])
            error = None
        except Exception as e:
            outcome = {"answer_text": "", "metadata": {}}
            error = str(e)
        elapsed = round(time.time() - t0, 2)

        record = {
            "id": item["id"],
            "language": item["language"],
            "type": item["type"],
            "question": item["question"],
            "expected_answer": item.get("expected_answer"),
            "_chunk_id": item.get("_chunk_id"),
            "answer_text": outcome["answer_text"],
            "guardrail_action": outcome["metadata"].get("guardrail_action"),
            "retrieved_chunks": outcome["metadata"].get("retrieved_chunks", []),
            "sources": outcome["metadata"].get("sources", []),
            "elapsed_s": elapsed,
            "error": error,
        }
        results.append(record)
        status = error or record["guardrail_action"]
        print(f"[{i}/{len(dataset)}] {item['id']} ({item['language']}/{item['type']}) "
              f"-> {status} ({elapsed}s)")

    Path("eval/task3_answer_quality/generated_answers.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n[SAVED] eval/task3_answer_quality/generated_answers.json")

    failed = [r for r in results if r["error"]]
    if failed:
        print(f"\n[WARNING] {len(failed)} requests errored -- rerun or investigate before judging.")
        for r in failed:
            print(f"  {r['id']}: {r['error']}")


if __name__ == "__main__":
    run()
