# Answer Quality Report

## Method

All 80 items in `eval/task1_dataset/dataset_v1.json` were sent through the real, live `/ask` endpoint (`app/api/main.py`) -- not simulated -- so every answer here is exactly what a customer would actually receive.

The 64 answerable items were scored on 4 checks by an LLM judge (`openai/gpt-oss-20b`, a different model/architecture from the generator `qwen/qwen3.8-27b`, to avoid self-evaluation bias). The 16 `should_refuse` items have no "answer quality" to score; they're checked logically (did the guardrail actually refuse: `out_of_domain` / `ambiguous` / `no_info`).

Judge prompts: `prompts/judge_faithfulness.txt`, `judge_relevance.txt`, `judge_completeness.txt`, `judge_language_correctness.txt`. Each returns a `{"score": 0.0-1.0, "reason": "..."}` pair per check per item -- raw data in `answer_quality_raw.json`.

Retrieval backend for this run: `bge_m3` (production default), hybrid mode (vector + BM25 + RRF fusion).

---

## 1. Overall scores, by language

| Language | n | Faithfulness | Relevance | Completeness | Language correctness |
|---|---:|---:|---:|---:|---:|
| English | 32 | 1.000 | 0.802 | 0.778 | 0.877 |
| Arabic | 32 | 0.969 | 0.859 | 0.792 | 0.787 |

| Gap (Arabic - English) | Faithfulness | Relevance | Completeness | Language correctness |
|---|---:|---:|---:|---:|
| **Difference** | -0.031 | +0.057 | +0.014 | **-0.090** |

**Explanation:**
- **Faithfulness** is the strongest metric in both languages, and the gap is small (Arabic 0.031 lower) -- the system rarely invents facts in either language.
- **Relevance** and **Completeness** are actually slightly *better* in Arabic than English in this run.
- **Language correctness is the widest and most product-relevant gap** (Arabic 0.090 lower). This is the check the task brief calls out specifically -- "is the Arabic actually correct rather than a literal translation that reads badly." See section 5 (worst-10 answers) for concrete examples.

---

## 2. Hallucination rate, by language

Defined here as the share of answerable items scoring faithfulness < 0.8 (i.e. containing at least one claim the judge flagged as not grounded in the retrieved context).

| Language | n | Hallucinated items | Rate |
|---|---:|---:|---:|
| English | 32 | 0 | 0.0% |
| Arabic | 32 | 1 (`ar-multi-015`) | 3.1% |

**Explanation:**
- Zero hallucinations found in English across all 32 answerable items.
- The one Arabic hallucination is partial, not a fabricated fact from nowhere: the model over-stated what Google Pay is, beyond what the retrieved chunk literally said (full breakdown in section 5, item 7).

---

## 3. should_refuse correctness, by language

| Language | n | Correctly refused | Rate |
|---|---:|---:|---:|
| English | 8 | 5 | 62.5% |
| Arabic | 8 | 7 | 87.5% |

**Explanation:**
- English refuses less reliably than Arabic here -- 3 of 8 English out-of-scope questions were answered anyway instead of refused.
- This points to a guardrail relevance-threshold/classification issue specific to English, not an embedding or language-fluency issue.

---

## 4. Scores by question type and language

| Type_Language | n | Faithfulness | Relevance | Completeness | Language correctness |
|---|---:|---:|---:|---:|---:|
| exact_value_en | 8 | 1.000 | 0.981 | 0.888 | 0.869 |
| simple_factual_en | 12 | 1.000 | 0.758 | 0.833 | 0.838 |
| exact_value_ar | 8 | 1.000 | 0.975 | 0.788 | 0.856 |
| simple_factual_ar | 12 | 1.000 | 0.900 | 0.819 | 0.804 |
| multi_chunk_en | 8 | 1.000 | 0.869 | 0.731 | 0.913 |
| multi_chunk_ar | 8 | 0.913 | 0.925 | 0.850 | 0.831 |
| dialect_arabizi_ar | 4 | 1.000 | 0.600 | 0.750 | 0.725 |
| informal_en | 4 | 1.000 | 0.575 | 0.500 | 0.900 |

**Explanation:**
- **Weakest cell: `informal_en`** (relevance 0.575, completeness 0.500, n=4). All 4 items are informal/colloquial English phrasings ("so like, ... or what") that tripped the ambiguity guardrail into asking a clarifying question instead of answering a question that was actually answerable.
- **`dialect_arabizi_ar` shows the same pattern** (relevance 0.600) -- confirms the ambiguity classifier is oversensitive to informal/non-standard phrasing generally, independent of language.
- Every other cell scores relevance/completeness at 0.73 or higher.

---

## 5. The 10 worst answers, analysed

Ranked by the average of the 4 scores.

| # | ID | Lang | Type | Avg score | Faith | Rel | Comp | Lang.corr |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | `en-simple-012` | en | simple_factual | 0.250 | 1.0 | 0.0 | 0.0 | 0.0 |
| 2 | `en-multi-002` | en | multi_chunk | 0.525 | 1.0 | 0.1 | 0.0 | 1.0 |
| 3 | `en-dialect-005` | en | informal | 0.525 | 1.0 | 0.2 | 0.0 | 0.9 |
| 4 | `en-dialect-008` | en | informal | 0.525 | 1.0 | 0.2 | 0.0 | 0.9 |
| 5 | `en-simple-014` | en | simple_factual | 0.537 | 1.0 | 0.2 | 0.0 | 0.95 |
| 6 | `ar-dialect-001` | ar | dialect_arabizi | 0.575 | 1.0 | 0.4 | 0.0 | 0.9 |
| 7 | `ar-multi-015` | ar | multi_chunk | 0.600 | 0.3 | 0.7 | 0.5 | 0.9 |
| 8 | `ar-simple-016` | ar | simple_factual | 0.700 | 1.0 | 0.9 | 0.0 | 0.9 |
| 9 | `ar-simple-010` | ar | simple_factual | 0.725 | 1.0 | 0.2 | 1.0 | 0.7 |
| 10 | `ar-dialect-003` | ar | dialect_arabizi | 0.725 | 1.0 | 0.2 | 1.0 | 0.7 |

### Item-by-item explanation

**1. `en-simple-012`** -- "Was this page helpful ?"
The "expected answer" scraped from the source page is UI chrome ("Yes / No / form-qMnCN4FNzB2XDXOzXtc4nKRX1 / webform_submission_help_feedback_tax..."), not real content. There is no genuine informational answer in the corpus, so the system correctly refuses. **This is a dataset problem, not a system problem.** Separately, the judge's `language_correctness=0.0` reason ("Answer is in English, not Arabic") is factually wrong -- both question and answer are English. A real judge scoring error, flagged for `judge-validation.md`.

**2. `en-multi-002`** -- "Who can get it and how long does it take to set up?"
Guardrail classified this as `ambiguous` and asked which service (broadband vs Orange Money) instead of answering. The question is short on explicit subject; a real conversation's prior turns would normally disambiguate it, but this eval is single-turn.

**3. `en-dialect-005`** -- "so like, how long does it take for my bill to be processed or what"
Same ambiguity-guardrail pattern -- informal phrasing triggered a clarifying question even though the question has one clear, answerable topic.

**4. `en-dialect-008`** -- "so like, was this page helpful or what"
Same dataset issue as item 1 (no real answer exists in the corpus) plus informal phrasing -- system correctly refuses.

**5. `en-simple-014`** -- "What is the minimum amount i can pay?"
Guardrail again asked which service (bill vs wallet) instead of answering -- same ambiguity-oversensitivity pattern as items 2-3.

**6. `ar-dialect-001`** -- "kif ba2dar atchek 3ala el package w shu ba2i minha?" (Arabizi)
Same ambiguity pattern on an Arabizi query (package vs roaming limit) -- confirms the oversensitivity is language-independent, not Arabic-specific.

**7. `ar-multi-015`** -- "ما هي Google Pay وهل يمكنني اضافه بطاقه Orange Money Visa الى Google Pay؟"
The only real **hallucination** in the whole run (faithfulness 0.3). The answer describes Google Pay as "a service that lets you pay with your phone via Google Wallet" -- a reasonable-sounding but slightly over-stated generalization the retrieved chunk didn't literally make. Worth a prompt-level fix for definitional questions (stick closer to source wording).

**8. `ar-simple-016`** -- "هل يمكنني شراء اكثر من حزمه تجوال انترنت في نفس الوقت؟"
Answered correctly and faithfully, but missed one part of the two-part reference answer (the roaming-bill-control app feature). A completeness gap, not a correctness one.

**9. `ar-simple-010`** -- "ما هو الجديد في خدمه الاتصال الصوتي الرقمي مع الفايبر؟"
Near-verbatim restatement of the source, faithful and complete, but doesn't explicitly frame the answer as "what's new" (relevance 0.2) -- the source itself doesn't contrast old-vs-new. Judge also flagged `"على الفايبر بوكس"` as an unnatural phrase (language_correctness 0.7) -- a real, minor fluency issue (calque of an English-style noun phrase into Arabic).

**10. `ar-dialect-003`**
Same source question and answer as item 9 (duplicate item, different phrasing bucket) -- identical failure mode.

---

## 6. Summary of real (non-dataset) weaknesses found

| # | Weakness | Evidence | Scope |
|---:|---|---|---|
| 1 | Ambiguity guardrail oversensitive to informal/short phrasing | 5 of 10 worst answers | Both languages |
| 2 | Genuine partial hallucination | 1 of 64 answerable items (1.6% overall, 3.1% Arabic) | Arabic only, this run |
| 3 | Language correctness is the widest en/ar gap | -0.090, mostly literal-translation phrasing | Arabic |
| 4 | English should_refuse reliability lower than Arabic | 62.5% vs 87.5% | English |
| 5 | Two dataset items have unusable "expected answers" | `en-simple-012`, `en-dialect-008` (scraped webform UI text) | Dataset, not system |

**Explanation:**
1. The ambiguity classifier's highest-impact fix opportunity -- it triggers on informal phrasing across both languages, not just Arabic dialect as might be assumed.
2. Low absolute hallucination rate overall; the single Arabic case was a partial over-generalization, not a fabricated fact.
3. Mostly minor calque-style phrasing (e.g. "على الفايبر بوكس"), not gross grammatical errors.
4. Worth checking the relevance-threshold tuning for English out-of-domain detection specifically.
5. Recommend pruning or fixing these two items in `dataset_v1.json` for future runs.
