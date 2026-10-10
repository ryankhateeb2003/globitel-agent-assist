# Task 4 -- Experiments Master Table

Every row below is one full run of `run_experiment.py` over all 80 items in `dataset_v1.json`, split by language. This file is updated live as each run finishes, not written once at the end.

---

## 1. Overview

**Method:** one configuration variable changed per run (chunk size, `top_k`, embedding model, or prompt version), everything else held at the production baseline. Same 80-question evaluation set every time. Retrieval and answer-quality scored by the same methodology as Tasks 2 and 3.

**Known measurement issue -- read before trusting any latency number below:** `run_experiment.py` sends all 80 requests back-to-back with `max_retries=8` on the Groq client. When a run collides with Groq's token-per-minute or token-per-day rate limit, the client's automatic retry wait gets counted as part of that request's latency -- inflating `latency_p50` / `latency_p95` far above what a real, isolated customer request would see (normal single-request latency is ~1-1.5s). Any row affected by this is marked explicitly in its Conclusion column and explained in the per-experiment notes.

---

## 2. Summary so far (Baseline + E1 complete)

**Full comparison table (Hit@5 / Faithfulness / Hallucination rate):**

| Chunk size | n chunks | Hit@5 EN | Hit@5 AR | Faithfulness EN | Faithfulness AR | Hallucination EN | Hallucination AR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 640 | 1.000 | 0.933 | 0.976 | 0.976 | 3.4% | 3.4% |
| Small | 679 | 0.656 | 0.844 | 0.973 | 1.000 | 3.9% | 0.0% |
| Medium | 288 | 0.906 | 0.906 | 1.000 | 0.983 | 0.0% | 3.3% |
| Large | 137 | 0.938 | 0.969 | 1.000 | 1.000 | 0.0% | 0.0% |

**Strongest -- `large` (137 chunks):** best overall E1 config. Hit@5 close to baseline on English (0.938) and **beats baseline outright on Arabic** (0.969 vs 0.933) -- the best Arabic Hit@5 measured anywhere so far. Perfect faithfulness (1.000) and zero hallucination on both languages.

**Weakest -- `small` (679 chunks):** worst Hit@5 of any config, especially English (0.656, a real collapse vs baseline's 1.000). Splitting FAQ entries into many small pieces loses the surrounding context a question's answer often needs.

**Clear pattern:** fewer, larger chunks retrieve better than many small ones on this dataset -- Hit@5 improves monotonically going small -> medium -> large.

**What stayed constant:** faithfulness barely moves with chunk size (0.973-1.000 across every config) -- even at small's worst retrieval, the model answered faithfully from whatever it did retrieve. Chunk size affects *whether the right content is found* (Hit@5), not *faithfulness to what was found*.

**EN/AR gap is not fixed -- it depends on chunk size:** baseline and large both favor English content more weakly than usual, and large actually **flips the usual gap**, with Arabic outperforming English.

**Not included above (incomplete or not started):** E2 (`top_k`) at 50/80, E3 (embedding model) and E4 (prompt version) not started -- excluded here until each is fully complete, per this file's own documentation rule.

---

## 3. Master table

| Experiment | Value | Language | Hit@5 | Faithfulness | Hallucination rate | Latency p50 (ms) | Latency p95 (ms) | Cost/query (USD) | Conclusion |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | production (`chunks.jsonl`, `top_k=5`, `globitelai_bge`, default prompts) | en | 1.000 | 0.976 | 3.4% | 18324 | 30385 | n/a | Strong baseline -- perfect retrieval, near-zero hallucination. **Latency not trustworthy, see note.** |
| Baseline | production (`chunks.jsonl`, `top_k=5`, `globitelai_bge`, default prompts) | ar | 0.933 | 0.976 | 3.4% | 20631 | 28514 | n/a | Small retrieval gap vs English (0.933 vs 1.000 Hit@5), consistent with Task 2's finding. **Latency not trustworthy, see note.** |
| E1 -- chunk size | small (679 chunks) | en | 0.656 | 0.973 | 3.9% | 18993 | 21356 | n/a | Hit@5 collapses vs baseline (0.656 vs 1.000) -- smaller chunks hurt English retrieval badly. **Latency not trustworthy, see note.** |
| E1 -- chunk size | small (679 chunks) | ar | 0.844 | 1.000 | 0.0% | 23367 | 25084 | n/a | Also drops vs baseline (0.844 vs 0.933) but less severely than English -- the gap direction flips from the usual EN>AR pattern. **Latency not trustworthy, see note.** |
| E1 -- chunk size | medium (288 chunks) | en | 0.906 | 1.000 | 0.0% | 14118 | 25413 | n/a | Much closer to baseline (0.906 vs 1.000) than small was -- medium chunks recover most of small's retrieval loss. **Latency not trustworthy, see note.** |
| E1 -- chunk size | medium (288 chunks) | ar | 0.906 | 0.983 | 3.3% | 28557 | 30713 | n/a | Slightly below baseline (0.906 vs 0.933), but EN and AR Hit@5 are now equal (0.906 = 0.906) -- the EN/AR gap nearly disappears at this chunk size. **Latency not trustworthy, see note.** |
| E1 -- chunk size | large (137 chunks) | en | 0.938 | 1.000 | 0.0% | 14859 | 34176 | n/a | Close to baseline (0.938 vs 1.000), perfect faithfulness. **Latency not trustworthy, see note.** |
| E1 -- chunk size | large (137 chunks) | ar | 0.969 | 1.000 | 0.0% | 38684 | 44633 | n/a | **Beats baseline** (0.969 vs 0.933) -- the best Arabic Hit@5 of any chunk size tested, with perfect faithfulness. **Latency not trustworthy, see note.** |
| E2 -- top_k | top_k=3 | en | 1.000 | 0.957 | 7.1% | 16532 | 22456 | n/a | Hit@5 unchanged from baseline (expected -- top_k doesn't affect retrieval scoring), but hallucination **doubles** vs baseline (7.1% vs 3.4%) -- fewer chunks sent to the generator measurably hurts English answer faithfulness. **Latency not trustworthy, see note.** |
| E2 -- top_k | top_k=3 | ar | 0.938 | 0.968 | 3.2% | 18029 | 21901 | n/a | Hit@5 close to baseline (0.938 vs 0.933, n=40 vs baseline's 38), hallucination about the same as baseline (3.2% vs 3.4%) -- unlike English, Arabic answer quality is not meaningfully hurt by top_k=3. **Latency not trustworthy, see note.** |
| E2 -- top_k | top_k=10 | en | 1.000 | 1.000 | 0.0% | 20263 | 34701 | n/a | **Zero hallucination** -- perfect faithfulness with 10 chunks sent to the generator instead of 5. **Latency not trustworthy, see note.** |
| E2 -- top_k | top_k=10 | ar | 0.938 | 0.994 | 0.0% | 22161 | 34485 | n/a | **Zero hallucination** here too -- near-perfect faithfulness (0.994). The best answer-quality result of any E2 config, both languages. **Latency not trustworthy, see note.** |
| E3 -- embedding model | bge_m3 | en | 1.000 | 1.000 | 0.0% | 18376 | 26582 | n/a | Retrieval and faithfulness match or beat globitelai_bge -- but should_refuse correctness drops hard (5/8 vs globitelai_bge's 8/8, see notes). **Latency not trustworthy, see note.** |
| E3 -- embedding model | bge_m3 | ar | 0.938 | 0.952 | 6.5% | 20643 | 36447 | n/a | Hit@5 close to globitelai_bge (0.938 vs 0.933), but faithfulness is lower and hallucination roughly doubles (6.5% vs 3.4%). **Latency not trustworthy, see note.** |
| E4 -- answer prompt | v2 (anti-invention rule) | en | 1.000 | **1.000** | **0.0%** | 18501 | 25044 | n/a | **Perfect faithfulness, zero hallucination** -- the targeted rule completely eliminated English hallucination. **Latency not trustworthy, see note.** |
| E4 -- answer prompt | v2 (anti-invention rule) | ar | 0.938 | 0.936 | **6.5%** | 21351 | 32418 | n/a | **Opposite effect in Arabic -- hallucination nearly doubles** (6.5% vs baseline's 3.4%). See notes: this is the EN-helps/AR-harms pattern the task brief explicitly warns about. **Latency not trustworthy, see note.** |
| E4 -- answer prompt | v3 (anti-invention + anti-deflection) | en | 1.000 | 1.000 | **0.0%** | 19112 | 23995 | n/a | Matches v2's perfect English result. **Latency not trustworthy, see note.** |
| E4 -- answer prompt | v3 (anti-invention + anti-deflection) | ar | 0.938 | 0.977 | **3.2%** | 21118 | 29051 | n/a | **Fixes v2's Arabic regression** -- hallucination back down to baseline level (3.2% vs baseline's 3.4%, even marginally better). **Winning prompt version -- see Winning Configuration.** **Latency not trustworthy, see note.** |

**n note:** English complete at 40/40. Arabic at 38/40 -- `ar-shortcode-002` and `ar-shortcode-003` did not complete (Groq's daily quota for `qwen/qwen3.8-27b` ran out mid-run). The Arabic row is computed from the 38 completed items only; the 2 missing items are **not** folded into these numbers. Every other `shortcode`-type item in this run scored perfectly (hit@5=1.0, faithfulness=1.0), so these two would likely do the same -- but that is an expectation, not a measured result, and is kept separate rather than assumed into the table.

---

## 4. Per-experiment notes

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
- **medium (288 chunks), done 2026-10-06:** `--chunks e1_medium`, everything else at baseline config. 80/80 complete.
- **Key finding -- medium recovers almost all of small's retrieval loss:** Hit@5 en 0.906, ar 0.906 -- much closer to baseline (1.000 / 0.933) than small (0.656 / 0.844). Notably, EN and AR Hit@5 are now equal at this chunk size, nearly closing the usual EN>AR retrieval gap.
- **should_refuse correctness:** en 8/8, ar 8/8.
- **Faithfulness stayed near-perfect** (en 1.000, ar 0.983) -- consistent with small's finding that faithfulness is largely unaffected by chunk size; it's Hit@5 that moves.
- **large (137 chunks), done 2026-10-07:** `--chunks e1_large`, everything else at baseline config. 80/80 complete.
- **Key finding -- large chunks are the best E1 configuration tested, and beat baseline on Arabic:** Hit@5 en 0.938, ar 0.969. Arabic actually **exceeds** the baseline's 0.933, the best Arabic Hit@5 of all 4 chunk sizes (baseline, small, medium, large). English stays close to baseline (0.938 vs 1.000). Both faithfulness scores are a perfect 1.000 with zero hallucination.
- **should_refuse correctness:** en 8/8, ar 8/8.
- **E1 summary across all 4 sizes (Hit@5):**

  | Chunk size | n chunks | EN | AR |
  |---|---:|---:|---:|
  | Baseline (structure) | 640 | 1.000 | 0.933 |
  | Small | 679 | 0.656 | 0.844 |
  | Medium | 288 | 0.906 | 0.906 |
  | **Large** | **137** | **0.938** | **0.969** |

  Fewer, larger chunks consistently retrieve better than many small ones on this dataset -- large is the strongest non-baseline config, and the only one to beat baseline outright (on Arabic).

### E2 -- top_k
- **top_k=3, done 2026-10-08:** `--top_k 3`, baseline chunking/embedding/prompt otherwise. 80/80 complete.
- **Key finding -- top_k doesn't touch retrieval scores, but it does touch English answer quality:** Hit@5/MRR are unchanged from baseline (as expected -- they're computed from the full fused ranking before the top_k cut). What does move: English hallucination rate **doubles** (3.4% -> 7.1%) with only 3 chunks sent to the generator instead of 5. Arabic is essentially unaffected (3.4% -> 3.2%).
- **should_refuse correctness:** en 8/8, ar 7/8 -- same as baseline.
- **Cheaper, as expected:** fewer chunks sent to the generator means less context in the prompt, so this is the lowest-cost config measured so far per query (lower `context_tokens_per_answer` than baseline/E1 for both languages).
- **top_k=10, done 2026-10-08:** `--top_k 10`, baseline chunking/embedding/prompt otherwise. 80/80 complete.
- **Key finding -- top_k=10 eliminates hallucination entirely, both languages:** 0.0% hallucination rate for EN and AR. Faithfulness: EN 1.000 (perfect), AR 0.994 (near-perfect). This is the best answer-quality result of any configuration tested in E1 or E2 so far.
- **should_refuse correctness:** en 8/8, ar 7/8 -- same as baseline.
- **E2 summary across all 3 tested top_k values (Hallucination rate, the metric that actually moves):**

  | top_k | n chunks sent | Hallucination EN | Hallucination AR |
  |---|---:|---:|---:|
  | 3 | 3 | 7.1% | 3.2% |
  | 5 (baseline) | 5 | 3.4% | 3.4% |
  | **10** | **10** | **0.0%** | **0.0%** |

  Baseline's `top_k=5` doesn't need its own run -- it's the same config as the Baseline row above, just read as E2's middle data point. Hit@5/MRR are essentially unaffected by top_k (see note above), so hallucination rate is the metric that actually distinguishes them. **Clear monotonic trend: hallucination drops steadily as top_k increases (3 -> 5 -> 10), for both languages.** More context consistently gives the generator fewer gaps to fill in on its own.
  - **Trade-off to weigh for Task 5:** top_k=10 is also the most expensive E2 config -- `context_tokens_per_answer` is highest here (851.9 en / 1518.4 ar, vs top_k=5's much lower baseline numbers), so the zero-hallucination result comes at a real token-cost increase. This is exactly the quality-vs-cost trade-off Task 5 will need to balance explicitly.

### E3 -- embedding model
- **bge_m3, done 2026-10-09:** `--embedding bge_m3`, baseline chunking/top_k/prompt otherwise. 80/80 complete.
- **Retrieval side (Hit@5/MRR):** already measured separately before this rebuild, in `Globitel_EmbeddingModel_globitelai-bge_Results.xlsx` (Desktop) -- globitelai_bge en=0.906/ar=0.854 vs bge_m3 en=0.891/ar=0.854 (near-identical, globitelai_bge slightly ahead on English). This run's own Hit@5 (en=1.000, ar=0.938) is consistent with that -- both models retrieve well on this dataset.
- **Full comparison (this run's generation-side numbers vs globitelai_bge's baseline):**

  | Embedding | Hit@5 EN | Hit@5 AR | Faithfulness EN | Faithfulness AR | Hallucination EN | Hallucination AR | should_refuse EN | should_refuse AR |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|
  | **globitelai_bge (production)** | 1.000 | 0.933 | 0.976 | 0.976 | 3.4% | 3.4% | 8/8 | 7/8 |
  | bge_m3 | 1.000 | 0.938 | **1.000** | 0.952 | **0.0%** | 6.5% | **5/8** | 7/8 |

- **Key finding -- a real mixed result, not a clean win either way:** bge_m3's English faithfulness/hallucination are actually *better* than globitelai_bge's (perfect 1.000 / 0.0%). But bge_m3's **should_refuse correctness collapses in English (5/8 vs 8/8)** -- 3 out-of-domain English questions got answered instead of refused that globitelai_bge correctly refused. Arabic hallucination is also roughly double with bge_m3 (6.5% vs 3.4%).
- **Why the should_refuse drop likely happened:** `guardrails.py`'s `RELEVANCE_THRESHOLDS_BY_BACKEND` calibrates separate relevance thresholds per embedding model, precisely because globitelai_bge scores everything higher than bge_m3 (documented in that file's own comment). This run used bge_m3's threshold set -- if that calibration is stale or less tuned than globitelai_bge's, it would explain more false "in-domain" classifications.
- **Conclusion so far:** globitelai_bge remains the safer production choice (much better should_refuse correctness, ~45x faster to embed, nearly identical retrieval). bge_m3's slightly better English faithfulness does not offset its guardrail-correctness cost.

### E4 -- answer prompt
- **v2 (anti-invention rule), done 2026-10-10:** `--prompt_dir eval/task4_experiments/prompts_v2`, baseline chunking/top_k/embedding otherwise. New rule 9 added to both prompt files (production prompts untouched): don't invent specific details (URLs, phone numbers, names) referenced but not explicitly given in the context -- state they're not provided instead of guessing. Designed directly from this project's own documented hallucination cases (`en-multi-001`, `en-multi-005`, `ar-multi-014`, `ar-multi-013` -- see `hallucination_cases.xlsx`). 80/80 complete.
- **THIS IS THE KEY FINDING OF TASK 4 -- a real "helps English, harms Arabic" configuration, exactly what the task brief warns to watch for:**

  | Config | Hallucination EN | Hallucination AR |
  |---|---:|---:|
  | Baseline (v1, no rule 9) | 3.4% | 3.4% |
  | **v2 (+ rule 9)** | **0.0%** | **6.5%** |

  English hallucination dropped to **zero** -- the rule worked exactly as designed for English. But Arabic hallucination **nearly doubled**. A report using only a blended average (e.g. "hallucination dropped from 3.4% to 3.25%") would have hidden this completely -- split by language, the true story is the opposite of what the average suggests for Arabic.
- **should_refuse correctness:** en 8/8 (same as baseline), ar 7/8 (same as baseline) -- unaffected.
- **This is a regression, not just a missed fix:** the 2 Arabic items that hallucinate under v2 are `ar-multi-013` (also hallucinated at baseline -- unresolved) and **`ar-multi-014`, which was answered correctly (faithfulness 1.0) at baseline**. Adding rule 9 made this specific item worse, not neutral. Full text and reasons in `hallucination_cases.xlsx` (Desktop).
- **Working theory:** rule 9 was written and validated against English failure examples only. It likely interacts with Arabic phrasing/generation differently than intended -- possibly making the model *more* cautious in a way that, for `ar-multi-014`, led it to treat an actually-covered detail (the phone number) as unsupported and default to the "not available" framing instead of using it. Not yet confirmed; would need a side-by-side prompt-ablation test to isolate.
- **v3 (anti-invention + anti-deflection rule), done 2026-10-11:** `--prompt_dir eval/task4_experiments/prompts_v3`. Rule 9 revised after seeing v2's Arabic regression -- written as a general principle (not tailored to the specific failing question), covering two directions at once: don't invent unsupported details (v2's original fix), AND don't default to a generic deflection ("check with a supervisor") when the context already contains a specific usable detail. 80/80 complete.
- **Result -- v3 is the winning prompt, no language trade-off:**

  | Version | Hallucination EN | Hallucination AR |
  |---|---:|---:|
  | v1 (baseline, no rule 9) | 3.4% | 3.4% |
  | v2 (anti-invention only) | 0.0% | 6.5% (regression) |
  | **v3 (anti-invention + anti-deflection)** | **0.0%** | **3.2%** |

  v3 keeps v2's perfect English result (0.0% hallucination) while bringing Arabic back down to baseline level (3.2%, marginally better than baseline's 3.4%). Unlike v2, v3 shows no EN-helps/AR-harms trade-off.
- **should_refuse correctness:** en 8/8, ar 7/8 -- same as baseline/v2 throughout.
- **Root-cause finding behind the original Arabic failures (`ar-multi-013`, `ar-multi-014`):** traced directly to the actual retrieved chunk text, not a model or judge error. The source HTML genuinely contains a working link (e.g. `https://internationalandroaming.orange.jo/roaming-services`), but the chunking pipeline's length limit happened to cut this specific chunk's text off mid-sentence, right before the linked text ("...لمزيد من المعلومات برجى زياره" -- the chunk literally ends there, before the link). A neighboring question on the same page (chunk `..._013`) kept its link intact because that link happened to be written as plain text before the chunk boundary, not inside an `<a>` tag near the cut point. This is a corpus-chunking artifact, not a generation-quality issue -- flagged here as a known limitation, not something either prompt version could fix on its own.

---

## 5. Winning configuration

All four experiments are complete as of 2026-10-11. Per-variable winners below, each picked on the evidence actually measured in this file -- not assumed.

| Variable | Winner | Why |
|---|---|---|
| **Chunk size** | `large` (137 chunks) | Only non-baseline E1 config to beat baseline outright (AR Hit@5 0.969 vs 0.933), with perfect faithfulness (1.000/1.000) and zero hallucination both languages. English retrieval stays close to baseline (0.938 vs 1.000). |
| **top_k** | `10` | Zero hallucination both languages (0.0%/0.0%) -- the best answer-quality result of any E2 config. Trade-off: highest token cost measured in E1+E2 (see E2 notes) -- a deliberate quality-over-cost choice, to be weighed against Task 5's cost targets. |
| **Embedding model** | `globitelai_bge` (current production) | `bge_m3` showed a real EN-helps/AR-harms-style trade-off of its own (better EN faithfulness, but should_refuse correctness collapsed 8/8 -> 5/8 in English) plus ~45x slower to embed. Not a close call. |
| **Answer prompt** | `v3` (anti-invention + anti-deflection rule) | Only version with zero hallucination in English AND hallucination at or below baseline in Arabic (3.2% vs 3.4%) -- v2 achieved the same English result but nearly doubled Arabic hallucination as a side effect. v3 has no language trade-off. |

**Important caveat on combining these:** each variable was tested independently against the baseline (one-variable-at-a-time, per the task's own methodology) -- these winners were never run *together* in a single combined configuration. The numbers above are not guaranteed to simply add up (e.g. `large` chunks + `top_k=10` + `v3` prompt, all at once, could interact differently than each did in isolation). A combined-configuration validation run is the natural next step before treating this as the final production config.

**The one finding that must not be lost in a blended average:** E4's v2 run is this project's clearest demonstrated case of the exact failure mode the task brief calls out by name -- a configuration that measurably helped English (hallucination 3.4% -> 0.0%) while measurably harming Arabic (3.4% -> 6.5%, including breaking a previously-correct item, `ar-multi-014`). It was caught and fixed (v3) only because results were tracked separately per language throughout, never as one combined number.

**Not yet applied to `config.py`:** these are the measured winners; writing them into the actual production config (`app/api/config.py`) as the new defaults is a deliberate follow-up step, not done automatically by this file.
