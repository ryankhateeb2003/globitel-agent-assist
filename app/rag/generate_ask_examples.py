"""
Task 4 deliverable: ask-examples.md data.

Samples 10 English + 10 Arabic real FAQ questions from chunks.jsonl
(same sampling approach as Task 3's eval_retrieval.py, seed=42 for
reproducibility), sends each one through the actual /ask endpoint
(not an internal function call -- the real HTTP API), and records the
question, answer, detected language, and sources for each.
"""

import json
import random
import time
import requests

random.seed(42)

API_URL = "http://localhost:8000/ask"


def extract_question(chunk_text: str) -> str | None:
    first_line = chunk_text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_question_set(n_per_language: int = 10) -> list[dict]:
    records = load_chunks()

    candidates = {"en": [], "ar": []}
    for r in records:
        question = extract_question(r["text"])
        if question and len(question) > 8:
            candidates[r["language"]].append(question)

    selected = []
    for lang in ["en", "ar"]:
        pool = candidates[lang]
        sample_size = min(n_per_language, len(pool))
        for q in random.sample(pool, sample_size):
            selected.append({"language": lang, "question": q})

    return selected


def ask(question: str) -> dict:
    response = requests.post(API_URL, json={"question": question}, timeout=60)
    raw = response.text

    answer_part, _, metadata_part = raw.partition("---METADATA---")
    answer_part = answer_part.strip()

    metadata = json.loads(metadata_part.strip()) if metadata_part.strip() else {}

    return {
        "answer": answer_part,
        "detected_language": metadata.get("language"),
        "sources": metadata.get("sources", []),
        "token_usage": metadata.get("token_usage", {}),
    }


def run():
    questions = build_question_set(n_per_language=10)
    results = []

    for i, item in enumerate(questions, 1):
        print(f"[{i}/20] ({item['language']}) {item['question']}")
        try:
            result = ask(item["question"])
            results.append({**item, **result})
        except Exception as exc:
            print(f"  [ERROR] {exc}")
            results.append({**item, "answer": None, "error": str(exc)})

        time.sleep(1)  # stay comfortably under Groq's 30 RPM free-tier limit

    with open("ask_examples_raw.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[SAVED] {len(results)} results -> ask_examples_raw.json")


if __name__ == "__main__":
    run()