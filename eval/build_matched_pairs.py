"""
Part Two, Task 1 -- builds eval/matched_pairs.json: 20 EN/AR pairs
pointing at the SAME underlying FAQ entry (same topic, matching
chunk_index across the language-twin documents) -- lets retrieval-metrics
report a same-question EN vs AR score side by side, isolating "is a gap
caused by language or by the question being harder" per the PDF's
requirement.

Matches items already in eval/dataset_v1.json by (_topic, _chunk_id's
numeric suffix) -- the corpus's own doc-pair convention (Task 1/3):
en/ar docs about the same page share the same trailing chunk index for
the same FAQ entry (confirmed in Task 5's hybrid-results.md, e.g.
c4790bface4196b1_032 (en) / 97c3ba92a38eb494_031 (ar) for QR Payment).

Usage: python eval/build_matched_pairs.py (run AFTER build_dataset_part2.py)
"""

import json
from pathlib import Path


def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_question(text: str) -> str | None:
    first_line = text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def extract_answer(text: str) -> str:
    return "\n".join(text.splitlines()[1:]).strip()


def build_matched_pairs(dataset: list[dict], chunks: list[dict], n_pairs: int = 20) -> list[dict]:
    """
    Searches ALL English FAQ chunks (not just the 20 already sampled into
    dataset_v1.json, which isn't enough candidates to reliably reach 20
    matches) for an Arabic chunk on the same topic at the same
    chunk_index -- i.e. the same FAQ entry translated, not just the same
    topic in general.
    """
    en_by_id = {c["chunk_id"]: c["_chunk_id"] for c in []}  # unused, kept for clarity of intent below
    dataset_by_chunk_id = {item.get("_chunk_id"): item for item in dataset if item["language"] == "en"}

    ar_by_topic_index = {}
    for c in chunks:
        if c["language"] == "ar":
            ar_by_topic_index.setdefault((c["topic"], c["chunk_index"]), c)

    pairs = []
    seen_topics = set()
    for en_chunk in chunks:
        if en_chunk["language"] != "en":
            continue
        en_question = extract_question(en_chunk["text"])
        if not en_question:
            continue
        key = (en_chunk["topic"], en_chunk["chunk_index"])
        if key in seen_topics:
            continue
        ar_chunk = ar_by_topic_index.get(key)
        if not ar_chunk:
            continue
        ar_question = extract_question(ar_chunk["text"])
        if not ar_question:
            continue
        seen_topics.add(key)

        # Reuse the dataset_v1.json item's fields if this exact EN chunk
        # is already sampled there (keeps ids/answers consistent);
        # otherwise build fresh from the chunk itself -- still real
        # corpus text either way.
        existing = dataset_by_chunk_id.get(en_chunk["chunk_id"])
        en_answer = existing["expected_answer"] if existing else extract_answer(en_chunk["text"])

        pairs.append({
            "pair_id": f"pair-{len(pairs)+1:03d}",
            "topic": en_chunk["topic"],
            "en": {
                "question": en_question,
                "expected_answer": en_answer,
                "source_file": en_chunk["source_file"],
                "_chunk_id": en_chunk["chunk_id"],
            },
            "ar": {
                "question": ar_question,
                "expected_answer": extract_answer(ar_chunk["text"]),
                "source_file": ar_chunk["source_file"],
                "_chunk_id": ar_chunk["chunk_id"],
            },
        })
        if len(pairs) >= n_pairs:
            break

    return pairs


if __name__ == "__main__":
    dataset = json.loads(Path("eval/dataset_v1.json").read_text(encoding="utf-8"))
    chunks = load_chunks()

    pairs = build_matched_pairs(dataset, chunks, n_pairs=20)
    print(f"[BUILT] {len(pairs)}/20 matched pairs")

    out_path = Path("eval/matched_pairs.json")
    out_path.write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SAVED] {out_path}")
