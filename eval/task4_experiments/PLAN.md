# Task 4 -- Execution Plan

One page to track exactly where we are and what's next. Updated as we go.

---

## Ground rules (agreed, don't break these)

1. **No restarts from scratch.** Every run resumes from its saved checkpoint (`--name` skips already-done ids). Partial progress is never discarded.
2. **No partial/mixed experiments.** Every experiment ships with its full pipeline (retrieval + faithfulness + hallucination), not a retrieval-only stand-in. retrieval-only mode stays unused unless explicitly asked for again.
3. **No cost column.** `cost_per_query_usd` stays `n/a` everywhere, always.
4. **Nothing runs without an explicit "تم".** No background command gets launched on its own.
5. **Document immediately.** The moment a run finishes (or stops on quota), its row goes into `experiments.md` the same turn -- not batched at the end.
6. **Latency from a quota-stressed run is not trustworthy** (Groq's `max_retries=8` backoff gets counted as request time). Every row's latency is flagged until a separate clean measurement pass is done at the end.
7. **Before launching a full run, do one cheap probe call first** to sanity-check the daily quota has real headroom -- avoids burning a launch that dies 2 items in.

---

## Status snapshot

| Run | Progress | State |
|---|---|---|
| `baseline` | 78/80 | done (2 AR shortcode items missing, quota) |
| `e1_small` | 40/80 | **paused, resume next** |
| `e2_top3` | 44/80 | paused |
| `e1_medium` | 0/80 | not started |
| `e1_large` | 0/80 | not started |
| `e2_top10` | 0/80 | not started |
| `e3_bge_m3` | 0/80 | not started (retrieval side already in hand from `Globitel_EmbeddingModel_globitelai-bge_Results.xlsx`, full pipeline still needed) |
| E4 prompt v2/v3 | not written | need to draft prompt variant files first (zero quota cost) |
| `e4_v2`, `e4_v3` | 0/80 each | not started |
| Clean latency pass | not done | separate small-sample run, done last, on a quota-healthy moment |
| Winning config (`config.py`) | not written | last step, after all of the above |

---

## Execution order (resume-first, cheapest-to-finish first)

1. **`e1_small`** -- resume 40 -> 80
2. **`e2_top3`** -- resume 44 -> 80
3. **`e3_bge_m3`** -- new, full pipeline (retrieval numbers already verified separately, just need faithfulness/hallucination side)
4. **`e1_medium`** -- new, full pipeline
5. **`e1_large`** -- new, full pipeline
6. **`e2_top10`** -- new, full pipeline
7. **E4 prompt variants** -- write v2/v3 text files (no quota), then run `e4_v2`, `e4_v3`
8. **Clean latency measurement** -- small sample, quota-healthy window
9. **Winning configuration** -- fill in `experiments.md` section 4 + `config.py` with justifying comment
10. -> Task 4 closed, move to Task 5

---

## Per-run checklist (repeat for each item above)

- [ ] Probe quota with a 1-token test call first
- [ ] Get explicit "تم" before launching
- [ ] Run in background, monitor
- [ ] On completion (full or quota-stopped): update `experiments.md`'s master table + per-experiment notes immediately
- [ ] Note in the table whether this row's latency is contaminated (it will be, until step 8)
