"""
Part Two, Task 2 -- turns eval/task2_retrieval_metrics/retrieval_metrics_raw.json into
retrieval-metrics-report.md: full metric table, per-type breakdown,
matched-pair EN/AR comparison, 10 worst questions, and the one explicit
"weakest language+type combo" statement the PDF asks for.

Usage: python eval/task1_dataset/build_retrieval_report.py (run AFTER retrieval_metrics.py)
"""

import json
from pathlib import Path

from app.retrieval.retrieval import search

K_VALUES = [1, 3, 5, 10]


def fmt_table(summary: dict, row_label_name: str) -> list[str]:
    lines = [
        f"| {row_label_name} | n | MRR | " + " | ".join(f"Hit@{k}" for k in K_VALUES)
        + " | " + " | ".join(f"Recall@{k}" for k in K_VALUES)
        + " | " + " | ".join(f"Precision@{k}" for k in K_VALUES) + " |",
        "|---|" + "---:|" * (2 + 3 * len(K_VALUES)),
    ]
    for label, m in summary.items():
        row = [str(label), str(m["n"]), f"{m['mrr']:.3f}"]
        row += [f"{m[f'hit@{k}']:.2f}" for k in K_VALUES]
        row += [f"{m[f'recall@{k}']:.2f}" for k in K_VALUES]
        row += [f"{m[f'precision@{k}']:.2f}" for k in K_VALUES]
        lines.append("| " + " | ".join(row) + " |")
    return lines


def main():
    raw = json.loads(Path("eval/task2_retrieval_metrics/retrieval_metrics_raw.json").read_text(encoding="utf-8"))
    dataset = {item["id"]: item for item in json.loads(Path("eval/task1_dataset/dataset_v1.json").read_text(encoding="utf-8"))}

    lines = [
        "# Retrieval Metrics Report",
        "",
        "## Method",
        "",
        "Every non-`should_refuse` item in `eval/task1_dataset/dataset_v1.json` (72 of 80 -- "
        "`should_refuse` items have no correct chunk to rank, by design) was run "
        "through `app/retrieval/retrieval.py`'s `search()` in **hybrid** mode "
        "(the `/ask` default), at `top_k=10`, using the customer's raw question "
        "wording -- **without** the LLM query-normalization step `/ask` applies "
        "in production, to measure the retrieval algorithm's own baseline "
        "capability first.",
        "",
        "`multi_chunk` items have two correct chunk ids; hit@k counts a hit if "
        "EITHER is found in the top k, recall@k is the fraction of the two found.",
        "",
        "---",
        "",
        "## Overall, by language",
        "",
    ]
    lines += fmt_table(raw["by_language"], "Language")

    lines += [
        "",
        "---",
        "",
        "## By type and language",
        "",
    ]
    lines += fmt_table(raw["by_type_language"], "Type_Language")

    # --- Matched pairs comparison ---
    matched_pairs = json.loads(Path("eval/task1_dataset/matched_pairs.json").read_text(encoding="utf-8"))
    per_item = {r["id"]: r for r in raw["per_item"]}

    lines += [
        "",
        "---",
        "",
        "## Matched pairs -- same question, EN vs AR, side by side",
        "",
        "Each pair points at the identical FAQ entry in both languages "
        "(`eval/task1_dataset/matched_pairs.json`). Scored here by re-running retrieval "
        "directly on each pair's question text (these are not necessarily the "
        "same items already scored above, since matched_pairs.json was built "
        "independently -- see eval/task1_dataset/README.md).",
        "",
        "| Pair | Topic | EN Hit@5 | AR Hit@5 | EN rank | AR rank |",
        "|---|---|---:|---:|---:|---:|",
    ]

    mismatch_count = 0
    for pair in matched_pairs:
        en_result = search(pair["en"]["question"], mode="hybrid", top_k=5)
        ar_result = search(pair["ar"]["question"], mode="hybrid", top_k=5)
        en_ids = [r["chunk_id"] for r in en_result["results"]]
        ar_ids = [r["chunk_id"] for r in ar_result["results"]]
        en_hit = pair["en"]["_chunk_id"] in en_ids
        ar_hit = pair["ar"]["_chunk_id"] in ar_ids
        en_rank = en_ids.index(pair["en"]["_chunk_id"]) + 1 if en_hit else None
        ar_rank = ar_ids.index(pair["ar"]["_chunk_id"]) + 1 if ar_hit else None
        if en_hit != ar_hit:
            mismatch_count += 1
        lines.append(
            f"| {pair['pair_id']} | {pair['topic']} | "
            f"{'yes' if en_hit else 'no'} | {'yes' if ar_hit else 'no'} | "
            f"{en_rank or '-'} | {ar_rank or '-'} |"
        )

    lines += [
        "",
        f"**{mismatch_count}/20 matched pairs disagree between languages on Hit@5** "
        "(one language found the identical FAQ entry, the other didn't) -- on identical "
        "questions, that gap is attributable to the language itself, not question difficulty.",
    ]

    # --- 10 worst questions ---
    scored = sorted(raw["per_item"], key=lambda r: r["mrr"])[:10]
    lines += [
        "",
        "---",
        "",
        "## 10 worst questions",
        "",
    ]
    for r in scored:
        item = dataset.get(r["id"], {})
        lines.append(
            f"- **{r['id']}** ({r['language']}/{r['type']}, MRR={r['mrr']:.2f}) "
            f"-- \"{item.get('question', '')[:80]}\" -- "
            f"correct chunk found at rank {r['first_hit_rank'] or 'not in top 10'}"
        )

    # --- Weakest combo statement ---
    weakest = min(raw["by_type_language"].items(), key=lambda kv: kv[1]["hit@5"])
    lines += [
        "",
        "---",
        "",
        "## Weakest language + type combination",
        "",
        f"**{weakest[0]}** -- Hit@5 = {weakest[1]['hit@5']:.2f}, MRR = {weakest[1]['mrr']:.3f} "
        f"(n={weakest[1]['n']}). This is the exact cell to prioritize in Task 4's experiments.",
    ]

    Path("eval/task2_retrieval_metrics/retrieval-metrics-report.md").write_text("\n".join(lines), encoding="utf-8")
    print("[SAVED] eval/task2_retrieval_metrics/retrieval-metrics-report.md")
    print(f"Matched-pair language disagreements: {mismatch_count}/20")
    print(f"Weakest combo: {weakest[0]} (hit@5={weakest[1]['hit@5']:.2f})")


if __name__ == "__main__":
    main()
