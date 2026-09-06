"""
Part Two, Task 1 -- generates dataset-stats.md from eval/dataset_v1.json
and eval/matched_pairs.json: counts per type per language, coverage
across source pages, and which pages are not covered yet.

Usage: python eval/build_stats.py (run last, after the dataset is final)
"""

import json
from collections import Counter
from pathlib import Path

ALL_CORPUS_TOPICS = [
    "mobile-lines", "fiber-adsl", "orange-money",
    "international-roaming", "bills-payment", "short-codes", "help-center",
]


def main():
    dataset = json.loads(Path("eval/dataset_v1.json").read_text(encoding="utf-8"))
    matched_pairs = json.loads(Path("eval/matched_pairs.json").read_text(encoding="utf-8"))

    type_lang_counts = Counter((d["type"], d["language"]) for d in dataset)
    topics_covered = Counter(d["_topic"] for d in dataset if d.get("_topic"))
    missing_topics = [t for t in ALL_CORPUS_TOPICS if t not in topics_covered]

    lines = [
        "# Dataset Statistics -- eval/dataset_v1.json",
        "",
        f"**Total items:** {len(dataset)}",
        f"**Matched pairs:** {len(matched_pairs)}/20",
        "",
        "## Counts per type, per language",
        "",
        "| Type | English | Arabic |",
        "|---|---:|---:|",
    ]

    all_types = sorted({d["type"] for d in dataset})
    for t in all_types:
        en_count = type_lang_counts.get((t, "en"), 0)
        ar_count = type_lang_counts.get((t, "ar"), 0)
        lines.append(f"| {t} | {en_count} | {ar_count} |")

    lines += [
        "",
        "## Coverage across source pages (topics)",
        "",
        "| Topic | Items sampled from it |",
        "|---|---:|",
    ]
    for topic in ALL_CORPUS_TOPICS:
        lines.append(f"| {topic} | {topics_covered.get(topic, 0)} |")

    lines += [
        "",
        "## Blind spots",
        "",
    ]
    if missing_topics:
        lines.append(f"**Topics with zero sampled items:** {', '.join(missing_topics)} "
                      "-- retrieval/answer-quality metrics in Task 2/3 will have no signal at all "
                      "for these pages; either they had no clean question-line chunks to sample from, "
                      "or random sampling simply didn't pick one. Worth a manual top-up pass before "
                      "treating Task 2's per-topic numbers as complete.")
    else:
        lines.append("All 7 corpus topics have at least one sampled item.")

    lines += [
        "",
        "`should_refuse` items intentionally have `expected_answer: null`, `source_file: null` -- ",
        "there is no correct chunk for them by design; the correct system behavior is refusal itself.",
    ]

    Path("eval/dataset-stats.md").write_text("\n".join(lines), encoding="utf-8")
    print("[SAVED] eval/dataset-stats.md")
    print(f"Missing topics: {missing_topics}")


if __name__ == "__main__":
    main()
