# Task 4 -- Experiments Master Table

Every row below is one full run of `run_experiment.py` over all 80 items in `dataset_v1.json`, split by language. This file is updated live as each run finishes, not written once at the end.

---

## 1. Overview

**Method:** one configuration variable changed per run (chunk size, `top_k`, embedding model, or prompt version), everything else held at the production baseline. Same 80-question evaluation set every time. Retrieval and answer-quality scored by the same methodology as Tasks 2 and 3.

**Known measurement issue -- read before trusting any latency number below:** `run_experiment.py` sends all 80 requests back-to-back with `max_retries=8` on the Groq client. When a run collides with Groq's token-per-minute or token-per-day rate limit, the client's automatic retry wait gets counted as part of that request's latency -- inflating `latency_p50` / `latency_p95` far above what a real, isolated customer request would see (normal single-request latency is ~1-1.5s). Any row affected by this is marked explicitly in its Conclusion column and explained in the per-experiment notes.

---

## 2. Master table

| Experiment | Value | Language | Hit@5 | Faithfulness | Hallucination rate | Latency p50 (ms) | Latency p95 (ms) | Cost/query (USD) | Conclusion |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | production (`chunks.jsonl`, `top_k=5`, `globitelai_bge`, default prompts) | en | 1.000 | 0.976 | 3.4% | 18324 | 30385 | n/a | Strong baseline -- perfect retrieval, near-zero hallucination. **Latency not trustworthy, see note.** |
| Baseline | production (`chunks.jsonl`, `top_k=5`, `globitelai_bge`, default prompts) | ar | 0.933 | 0.976 | 3.4% | 20631 | 28514 | n/a | Small retrieval gap vs English (0.933 vs 1.000 Hit@5), consistent with Task 2's finding. **Latency not trustworthy, see note.** |
| E1 -- chunk size | small (679 chunks) | en | 0.656 | 0.973 | 3.9% | 18993 | 21356 | n/a | Hit@5 collapses vs baseline (0.656 vs 1.000) -- smaller chunks hurt English retrieval badly. **Latency not trustworthy, see note.** |
| E1 -- chunk size | small (679 chunks) | ar | 0.844 | 1.000 | 0.0% | 23367 | 25084 | n/a | Also drops vs baseline (0.844 vs 0.933) but less severely than English -- the gap direction flips from the usual EN>AR pattern. **Latency not trustworthy, see note.** |

**n note:** English complete at 40/40. Arabic at 38/40 -- `ar-shortcode-002` and `ar-shortcode-003` did not complete (Groq's daily quota for `qwen/qwen3.8-27b` ran out mid-run). The Arabic row is computed from the 38 completed items only; the 2 missing items are **not** folded into these numbers. Every other `shortcode`-type item in this run scored perfectly (hit@5=1.0, faithfulness=1.0), so these two would likely do the same -- but that is an expectation, not a measured result, and is kept separate rather than assumed into the table.

---

## 3. Per-experiment notes

### Baseline
- **Config:** production `chunks.jsonl`, `top_k=5`, `embedding=globitelai_bge`, default prompts (`prompts/rag_answer_en.txt` / `_ar.txt`).
- **should_refuse correctness:** en 8/8, ar 7/8 -- consistent with Task 3's original result.
- **Latency contamination (important):** this run hit Groq's daily token quota for `qwen/qwen3.8-27b` twice (`Limit 200000, Used ~199500+`), and the retry/backoff wait each time got counted inside that request's `total` timing -- that's what pushed p50 to ~18-20s and p95 to ~28-30s, nowhere near the ~1-1.5s a single live `/ask` request actually takes. A clean latency number needs the run spaced out over time, or run on a fresh daily quota with nothing else competing for it.
- **2 Arabic items never completed** (`ar-shortcode-002`, `ar-shortcode-003`) -- the second quota collision ran out the day's budget before they could run. Excluded from the Arabic averages above, not assumed or fabricated; flagged for a retry once quota resets.

### E1 -- chunk size
- **small (679 chunks), done 2026-10-05:** `--chunks e1_small`, everything else at baseline config. 80/80 complete.
- **Key finding -- smaller chunks hurt retrieval badly, English worst:** Hit@5 drops from baseline's 1.000 -> 0.656 (en) and 0.933 -> 0.844 (ar). Smaller chunks mean each one carries less context, so a question whose answer needs surrounding context from the original FAQ entry more often misses entirely once that entry is split into several small pieces.
- **should_refuse correctness:** en 8/8, ar 8/8 -- unaffected by chunk size (refusal is a guardrail/classify_intent decision, not retrieval-dependent).
- **Faithfulness stayed high despite worse retrieval** (en 0.973, ar 1.000) -- when the model did get a relevant chunk, it answered faithfully from it; the chunk-size damage shows up in *whether* the right content was found at all (Hit@5), not in faithfulness to whatever was found.
- **medium (288 chunks) and large (137 chunks):** not started yet.

### E2 -- top_k
_(not started)_

### E3 -- embedding model
_(not started)_

### E4 -- answer prompt
_(not started)_

---

## 4. Winning configuration

_(filled in once all four experiments are complete -- see `config.py` for the final values this table justifies.)_
