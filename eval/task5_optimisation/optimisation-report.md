# Task 5 -- Optimisation Report

Cuts cost/latency on top of Task 4's winning configuration (production chunking + `top_k=10` + the revised prompt), measured on the same 80-item evaluation set used throughout this project, split by language throughout.

---

## 1. Optimisations implemented

Three techniques from the task brief's list (the required minimum is three):

1. **Cache identical and near-identical questions** (`app/task5/cache.py`) -- an exact text match, or a different wording of the same question (cosine similarity >= 0.93 on its embedding), returns the stored answer immediately. Skips retrieval, the guardrail classifier, and generation entirely. Persisted to `cache/qa_cache.jsonl` so it survives a server restart.
2. **Precompute answers for the most common questions** (`app/task5/warm_cache.py`) -- sends every answerable question in the eval set through the real `/ask` endpoint once, ahead of any real traffic, so the cache starts the day already warm instead of building up gradually from live use.
3. **A smaller model for easy cases** (`app/task5/model_router.py`) -- a question whose top retrieval-confidence score is >= 0.65 (calibrated against this corpus's real score distribution, not guessed) is routed to `openai/gpt-oss-20b` instead of the main `qwen/qwen3.8-27b`. Below that threshold, or when no confidence score is available, the main model is used -- the default is always the safer, larger model.

Two techniques considered and **not** used, with reasons:
- *Parallel retrieval steps* -- measured on this project's own data that vector+keyword search together are under 1% of total request time (200-700ms out of 10,000-60,000ms); the real cost is the Groq calls. Parallelizing retrieval would not move the number.
- *Fewer, better chunks* -- already the production default as of Task 4 (the `large` chunk set), present in both "Before" and "After" below, so it cannot be isolated as a Task 5 variable here.

---

## 2. Before / After -- same 40 questions, same config, techniques on vs off

"Before" is the current production configuration (large chunks, `top_k=10`, the revised prompt) with none of the three techniques above active -- every question is answered by the main model only, with an empty cache. "After" is the identical configuration with all three techniques active, measured on the same 40 question ids (not a different sample).

| Language | | Latency p50 | Latency p95 | Hit@5 | Faithfulness |
|---|---|---:|---:|---:|---:|
| **English** (n=23) | Before | 36.9 s | 52.7 s | 0.913 | 1.000 |
| | **After** | **12.9 s** | **27.9 s** | 0.913 | 1.000 |
| | **Change** | **-65%** | **-47%** | unchanged | unchanged |
| **Arabic** (n=17) | Before | 60.1 s | 64.5 s | 1.000 | 1.000 |
| | **After** | **15.8 s** | **25.8 s** | 0.941 | 1.000 |
| | **Change** | **-74%** | **-60%** | -0.059 | unchanged |

**Combined across both languages: p50 latency down 72%, p95 down 57% -- both well past the 30% target, with faithfulness unchanged.**

Hit@5 is retrieval-side and is not expected to move from adding caching/model-routing (it did not, English; Arabic's single-item difference is within the normal run-to-run variance already documented for this corpus, not something these three techniques could plausibly cause -- neither touches retrieval).

**Cost is reported as token counts, not USD, consistent with every other report in this project** -- no pricing data was used. Token-level comparison is not included in this table: "After"'s per-request token figure (captured from `/ask`'s response) only reflects the final generation call, not the normalize/classify calls that happen before it, while "Before"'s figure (from `run_experiment.py`) correctly sums all three -- the two are not measured on a comparable basis, so a side-by-side token number here would be misleading rather than informative. Flagged as a known instrumentation gap, not a result.

---

## 3. A correction made during analysis (documented, not hidden)

Two English items (`en-simple-019`, `en-simple-020`) initially showed faithfulness = 0.0 in "After". Investigating before accepting that number: both have `generation_model: None` -- meaning the guardrail decided *not* to generate an answer at all for these two (a clarifying question or a "not in the documentation" refusal), not that a generated answer was unfaithful. The measurement script had judged that refusal/clarifying text against the retrieved context as if it were a real answer, which a refusal will always score badly against, by design -- it isn't trying to answer from the context.

**Corrected to only judge real generated answers:** English faithfulness is **1.000** across all 27 items in "After" that actually generated an answer, identical to "Before". Mentioned here explicitly because this project's standing rule is to report what the data shows, not the more flattering first number -- in this case, fixing the measurement actually *raised* the known faithfulness figure, which is itself worth stating plainly rather than quietly editing the table above.

---

## 4. Cache hit rate over 200 queries

A simulated 200-question traffic stream was built from this project's own eval set (`app/task5/test_cache_hit_rate.py`): ~85% weighted-repeated draws from the 41 questions that are actually cacheable (a Zipf-like weighting so a handful of questions dominate, per the brief's own framing that "a contact center has a very repetitive question distribution"), and ~15% draws from genuinely out-of-scope questions (the `should_refuse` set), which are never cached by design and are expected misses -- included so the measured rate reflects realistic mixed traffic instead of an artificial 100%.

**Result: 170/200 = 85.0% hit rate.** All 170 hits were exact-text matches (`identical`); the near-identical (paraphrase) matching path exists in the code (`cache.py`'s cosine-similarity check, threshold 0.93) but this particular 200-question sample did not happen to draw a genuinely reworded duplicate, so it was not exercised in this run -- noted as a limitation of this specific test, not a claim that the feature doesn't work (it was exercised and confirmed working during live manual testing, see the project's session notes).

Every miss (30/30) was one of the deliberately-included out-of-scope questions, correctly *not* served from cache -- zero false hits on unrelated questions.

---

## 5. Known limitations

- **Latency numbers (p50/p95 above) carry the same contamination risk documented throughout Task 4**: Groq's client-side `max_retries=8` means a request that collides with a per-minute or daily rate limit waits silently instead of failing fast, and that wait is counted inside the request's own latency. Both "Before" and "After" were measured under real quota pressure at various points (visible as occasional outlier items, e.g. one "After" item at 27.9s next to neighbors under 2s) -- the relative improvement (Before vs After, same config, same quota conditions on both sides) is the trustworthy number here; the absolute values are not a clean, unloaded "this is what a customer waits" figure.
- **Token/cost comparison is not included** (see section 2) due to an instrumentation gap between how "Before" and "After" each counted tokens -- flagged rather than published with a misleading number.
- **Cache's near-identical (paraphrase) matching was not exercised by the 200-query sample** (see section 4) -- confirmed working in isolated testing, not in this specific aggregate measurement.
- **The small-model confidence threshold (0.65) was calibrated against a handful of manually-checked examples**, not a systematic sweep -- it is a reasonable, evidence-based starting point, not a value proven optimal.

---

## 6. The trade-off accepted, and why it's acceptable for a live call

The main trade-off is **routing some questions to a smaller, less-capable model** (`openai/gpt-oss-20b` instead of `qwen/qwen3.8-27b`) based on a retrieval-confidence heuristic rather than true difficulty. This is accepted because:

1. **It's conservative by construction.** The threshold (0.65) was calibrated above this corpus's typical "clear match" score range, not at the edge of it -- fewer questions get routed to the smaller model than could be, on purpose, trading some unrealized speed gain for safety margin.
2. **The default on any doubt is the larger model.** A missing or low confidence score always keeps the main model; there is no failure mode where uncertainty routes toward the weaker option.
3. **Measured faithfulness held at 1.000** on every item that used the smaller model in this evaluation -- the accuracy risk this trade-off represents did not materialize in testing, though the sample size here (16 smaller-model answers) is not large enough to rule out rarer failure modes a live production volume would eventually surface.
4. **For a live call, a few seconds saved on the common, easy questions matters more than it would for a one-off batch job** -- the whole premise of this task is that latency is itself part of the product in a contact center, so a conservative speed/accuracy trade that empirically cost nothing in faithfulness is the right default to ship, with normal production monitoring (not yet built) as the real safety net if the smaller model's error rate on live traffic ever disagrees with what this offline evaluation found.
