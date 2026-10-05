"""
Part Two, Task 1 -- builds eval/task1_dataset/dataset_v1.json: real question/answer
pairs sampled directly from chunks.jsonl (the same corpus indexed in
Part One), not invented. Same sampling approach as Task 5's
eval_hybrid.py's build_test_set() -- extended here to cover simple_factual
and exact_value automatically; multi_chunk, should_refuse, and
dialect/Arabizi need separate, more manual construction (see
build_dataset_manual.py) since they can't be pulled straight out of the
corpus the same way.

Usage: python eval/task1_dataset/build_dataset.py
"""

import json
import random
import re
from pathlib import Path

random.seed(42)  # reproducible sample -- same items every run

EXACT_VALUE_PATTERN = re.compile(
    r"\*\d+#|\d+\s*(?:دينار|JD|جنيه|%|دقيقه|دقيقة|minute|GB|جيجا|ميجا|MB)",
    re.IGNORECASE,
)

N_SIMPLE_FACTUAL_PER_LANG = 12
N_EXACT_VALUE_PER_LANG = 8


def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_question(text: str) -> str | None:
    """First line of the chunk, if it looks like a question (ends in
    ? or ؟) -- matches the FAQ structure chunk_text() built these
    chunks around in Part One."""
    first_line = text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def extract_answer(text: str) -> str:
    """Everything after the first line -- the answer body."""
    lines = text.splitlines()[1:]
    return "\n".join(lines).strip()


def build_candidates(chunks: list[dict]) -> dict:
    candidates = {"en": [], "ar": []}
    for c in chunks:
        question = extract_question(c["text"])
        if not question or len(question) <= 8:
            continue
        answer = extract_answer(c["text"])
        if not answer:
            continue  # a question line with nothing after it isn't usable as a Q&A pair
        candidates[c["language"]].append({
            "question": question,
            "expected_answer": answer,
            "source_file": c["source_file"],
            "source_section": question,  # the question line itself IDs the FAQ entry
            "chunk_id": c["chunk_id"],
            "topic": c["topic"],
            "has_exact_value": bool(EXACT_VALUE_PATTERN.search(c["text"])),
        })
    return candidates


def make_item(raw: dict, item_id: str, language: str, qtype: str, difficulty: str) -> dict:
    return {
        "id": item_id,
        "question": raw["question"],
        "expected_answer": raw["expected_answer"],
        "source_file": raw["source_file"],
        "source_section": raw["source_section"],
        "language": language,
        "type": qtype,
        "difficulty": difficulty,
        "_chunk_id": raw["chunk_id"],  # kept for traceability, not part of the PDF's required fields
        "_topic": raw["topic"],
    }


def stratified_sample_by_topic(pool: list[dict], n: int) -> list[dict]:
    """
    Round-robin across topics instead of pure random.sample() over the
    whole pool -- plain random sampling let orange-money (445 chunks)
    and international-roaming (83) drown out mobile-lines (19),
    bills-payment (24), and fiber-adsl (64) entirely by chance, leaving
    dataset_v1.json with zero items from half the corpus. This shuffles
    each topic's own candidates, then takes one from each topic in turn
    (skipping topics that have run out) until n items are picked -- every
    topic with ANY usable candidate gets a fair shot before a
    well-represented topic gets a second pick.
    """
    by_topic: dict[str, list[dict]] = {}
    for c in pool:
        by_topic.setdefault(c["topic"], []).append(c)
    for items in by_topic.values():
        random.shuffle(items)

    chosen = []
    topics = list(by_topic.keys())
    i = 0
    while len(chosen) < n and any(by_topic.values()):
        topic = topics[i % len(topics)]
        if by_topic[topic]:
            chosen.append(by_topic[topic].pop())
        i += 1
        if i > n * len(topics) + len(topics):
            break  # safety valve, shouldn't trigger in practice
    return chosen


def build_dataset() -> list[dict]:
    chunks = load_chunks()
    candidates = build_candidates(chunks)

    dataset = []
    counter = {"en": 0, "ar": 0}

    for lang in ["en", "ar"]:
        pool = candidates[lang]
        exact_pool = [c for c in pool if c["has_exact_value"]]
        other_pool = [c for c in pool if not c["has_exact_value"]]

        chosen_exact = stratified_sample_by_topic(exact_pool, N_EXACT_VALUE_PER_LANG)

        remaining_other = [c for c in other_pool if c not in chosen_exact]
        chosen_simple = stratified_sample_by_topic(remaining_other, N_SIMPLE_FACTUAL_PER_LANG)

        for raw in chosen_exact:
            counter[lang] += 1
            dataset.append(make_item(raw, f"{lang}-exact-{counter[lang]:03d}", lang, "exact_value", "medium"))

        for raw in chosen_simple:
            counter[lang] += 1
            dataset.append(make_item(raw, f"{lang}-simple-{counter[lang]:03d}", lang, "simple_factual", "easy"))

        topics_hit = sorted({c["topic"] for c in chosen_exact + chosen_simple})
        print(f"[{lang}] exact_value: {len(chosen_exact)}/{N_EXACT_VALUE_PER_LANG}, "
              f"simple_factual: {len(chosen_simple)}/{N_SIMPLE_FACTUAL_PER_LANG} "
              f"(pool sizes: exact={len(exact_pool)}, other={len(other_pool)}) "
              f"-- topics covered: {topics_hit}")

    return dataset


if __name__ == "__main__":
    dataset = build_dataset()
    out_path = Path("eval/task1_dataset/dataset_v1.json")
    out_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[SAVED] {out_path} -- {len(dataset)} items so far (simple_factual + exact_value only)")
    print("Still needed: multi_chunk, should_refuse, dialect/Arabizi -- see build_dataset_manual.py")
