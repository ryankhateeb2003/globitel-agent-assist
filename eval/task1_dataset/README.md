# Evaluation Dataset — eval/dataset_v1.json

Part Two, Task 1 deliverable. Builds a bilingual, corpus-grounded test set for
measuring the RAG pipeline built in Part One — see `../app/` for the system
under test.

## How it was built

Three scripts, run in order, each extending the previous file:

1. **`build_dataset.py`** — samples `simple_factual` (12/language) and
   `exact_value` (8/language) items directly from `chunks.jsonl` (the same
   corpus index the running system uses). A chunk's first line (the FAQ
   question) becomes `question`; everything after it becomes
   `expected_answer`. `exact_value` items are chunks matching a fee/limit/
   short-code pattern. Sampling uses a fixed random seed (42), so re-running
   it reproduces the same 40 items.
2. **`build_dataset_part2.py`** — adds the three categories that can't be
   pulled straight out of the corpus by simple sampling:
   - `multi_chunk` (8/language): auto-sampled pairs of adjacent,
     same-document FAQ entries (both real question lines), joined into one
     combined question. The combination wording is authored; both halves
     of the answer are the real chunk text, unedited.
   - `should_refuse` (8/language): reuses the exact `NEGATIVE_QUERIES`
     already measured in `../app/guardrails/tune_threshold.py` (Task 6,
     Part One) — genuinely unanswerable from this 7-topic corpus, and
     already confirmed to score low / get refused by the live system.
     `expected_answer` and `source_file` are `null` by design — there is no
     correct chunk, and the correct system behavior is refusal itself.
   - `dialect_arabizi` / `informal` (4/language): takes an already-sampled
     `simple_factual` item and rewrites only its `question` field in
     Arabizi (AR side) or casual spoken English (EN side) — same real
     answer and source as the item it's based on (see `_based_on_id`).
3. **`build_matched_pairs.py`** — finds 20 English/Arabic chunk pairs that
   are the *same* FAQ entry (same topic, same `chunk_index` in the
   language-twin document), not just the same topic in general. This is
   what lets `retrieval_metrics.py` (Task 2) report a same-question EN
   vs. AR score side by side.

`build_stats.py` (run last) generates `dataset-stats.md`.

## What it covers

The corpus has 7 topic pages: `mobile-lines`, `fiber-adsl`, `orange-money`,
`international-roaming`, `bills-payment`, `short-codes`, `help-center`. See
`dataset-stats.md` for exactly how many sampled items come from each —
**as of this version, 4 of the 7 have zero sampled items** (random sampling
over the whole corpus concentrated on `orange-money` and
`international-roaming`, which have the most FAQ-style chunks). This is a
known blind spot, not a hidden one: Task 2/3 metrics will have no signal at
all for the uncovered topics until a manual top-up pass adds items from them
specifically.

## Fields (per `dataset_v1.json` item)

| Field | Meaning |
|---|---|
| `id` | Unique id, e.g. `en-exact-003` |
| `question` | The question text |
| `expected_answer` | The correct answer (`null` for `should_refuse`) |
| `source_file` | Which corpus file it came from (`null` for `should_refuse`) |
| `source_section` | The FAQ heading(s) this traces back to |
| `language` | `en` or `ar` |
| `type` | `simple_factual`, `exact_value`, `multi_chunk`, `should_refuse`, `dialect_arabizi`, or `informal` |
| `difficulty` | `easy`, `medium`, or `hard` |
| `_chunk_id` | Underscore-prefixed = traceability only, not required by the task spec; the exact `chunks.jsonl` chunk_id(s) this item was built from |
| `_topic` | Underscore-prefixed, same reason; the corpus topic |

## Reproducing it

```bash
python eval/build_dataset.py         # 40 items: simple_factual + exact_value
python eval/build_dataset_part2.py   # +40 items: multi_chunk, should_refuse, dialect/informal -> 80 total
python eval/build_matched_pairs.py   # eval/matched_pairs.json, 20 pairs
python eval/build_stats.py           # eval/dataset-stats.md
```

Fixed random seeds mean re-running all four reproduces an identical
`dataset_v1.json` and `matched_pairs.json`, as long as `chunks.jsonl` itself
hasn't changed since.
