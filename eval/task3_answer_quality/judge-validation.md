# Judge Validation Report

## Method

A random sample of 40 judge decisions was drawn from the full 256 (64 answerable items x 4 checks) in `answer_quality_raw.json` -- **20 English + 20 Arabic** (seed=42, `judge_validation_sample.json`). Each decision is one specific check (Faithfulness / Relevance / Completeness / Language correctness) for one item, not a whole item.

Two review passes were done:
1. **Human review** (Ryan) -- read through all 40 decisions (question, context, answer, expected answer, judge score + reason) and independently assessed each.
2. **Independent AI-assisted second pass** (Claude) -- re-checked all 40 as a precautionary cross-check, specifically to catch anything a quick human pass might miss.

The two passes converged on the same 4 disagreements, all concentrated in the **Language correctness** check.

---

## Agreement rate, by language

| Language | n | Agree | Disagree | Agreement rate |
|---|---:|---:|---:|---:|
| English | 20 | 19 | 1 | 95.0% |
| Arabic | 20 | 17 | 3 | 85.0% |
| **Overall** | 40 | 36 | 4 | **90.0%** |

**Explanation:**
- All 4 disagreements are on the same check (Language correctness) -- Faithfulness, Relevance, and Completeness had zero disagreements across the full sample.
- Arabic has a lower agreement rate than English (85% vs 95%) -- consistent with the task brief's expectation that "an LLM judge is weaker at judging Arabic fluency than English fluency."

---

## Cases where the judge was wrong

### 1. `en-simple-012`
- **Question:** "Was this page helpful ?"
- **Answer:** "I don't have this information in the documentation. Please check with a supervisor or the relevant system."
- **Judge score:** 0.0 -- **Judge reason:** "Answer is in English, not Arabic"
- **Why it's wrong:** Factually incorrect. Both the question and the answer are English -- the judge's own stated reason is false. The system's answer language is actually correct.

### 2. `ar-multi-009`
- **Question:** "كيف استطيع استخدام الانترنت اثناء تواجدي خارج الاردن (التجوال) وكيف يمكنني معرفه حزم التجوال المتاحه لكل دوله؟"
- **Answer:** "للاستخدام الإنترنت أثناء التجوال، قم بتشغيل تجوال البيانات على هاتفك وتأكد من أن نقطة الوصول (APN) هي net.orange.jo. أما لمعرفة حزم التجوال المتاحة، فستصلك رسائل نصية عند وصولك للوجهة، أو يمكنك زيارة الرابط https://oran.ge/2r7cAjq."
- **Judge score:** 0.5 -- **Judge reason:** "Unnatural phrase: فستصلك رسائل نصية عند وصولك للوجهة"
- **Why it's wrong:** This phrase reads as normal, fluent Modern Standard Arabic to a native speaker -- not unnatural enough to justify a mid-range penalty.

### 3. `ar-simple-009`
- **Question:** "ما هي الخدمات التي يمكنني سداد فواتيرها؟"
- **Answer:** "يمكنك سداد فواتير عروض الجوال والثابت والانترنت في كل مكان، وخدمات ADSL والألياف، وبيت العيلة المتقاربة."
- **Judge score:** 0.3 -- **Judge reason:** "بيت العيلة المتقاربة غير طبيعية وغير مفهومة"
- **Why it's wrong:** This exact phrase is **copied verbatim from the retrieved context** (the source corpus itself uses it, likely a bundle/campaign name) -- the generation model did not invent it. Penalizing the system's language quality for reproducing the source's own wording is not a fair generation-quality signal.

### 4. `ar-exact-003`
- **Question:** "كيف يمكنني ايقاف الرسائل الدعائيه ؟"
- **Answer:** "اتصل على *112# لوقف الرسائل الدعائية."
- **Judge score:** 0.7 -- **Judge reason:** "Use of 'لوقف' instead of natural 'لإيقاف'"
- **Why it's wrong:** Same pattern as #3 -- "لوقف" appears **verbatim in the reference/context text itself**. The model faithfully reused the source's phrasing; this is not a generation fluency defect.

**Pattern found:** 2 of the 3 Arabic errors (#3, #4) share the same root cause -- the judge penalized the generation model for **faithfully reproducing wording taken directly from the retrieved context**, rather than judging the model's own generated phrasing. This suggests the `judge_language_correctness.txt` prompt should be adjusted to explicitly exempt content that is a direct quote/near-quote of the context from naturalness penalties.

---

## Separate finding (not a judge-scoring error): guardrail gap on `en-simple-012`

While reviewing case #1 above, a second, unrelated issue surfaced: the question "Was this page helpful?" has no real informational answer anywhere in the corpus (the "expected answer" is scraped webform UI text: "Yes / No / form-qMnCN4FNzB2XDXOzXtc4nKRX1..."). The system's `guardrail_action` for this item was **`answer_normally`**, not `out_of_domain` / `no_info` -- meaning the guardrail's own classification failed to catch that this question has no answerable content. The model itself then improvised a reasonable refusal ("I don't have this information...") on its own initiative, which happened to be the right call, but the guardrail should have caught this upstream rather than relying on the generation model to recover.

**This is a guardrail classification gap, not a judge-validation error or an answer-quality error** -- flagged here for `answer-quality-report.md` / Task 6's known-weaknesses list, not counted against the judge's agreement rate.

---

## Conclusion

- **Overall judge agreement: 36/40 (90.0%)** -- English 95.0%, Arabic 85.0%.
- All 4 disagreements are confined to the **Language correctness** check specifically; the judge's Faithfulness, Relevance, and Completeness scoring was fully agreed with across the sample.
- The judge is measurably weaker at Arabic fluency judgment than English (85% vs 95% agreement), matching the task brief's stated expectation -- and specifically, it has a tendency to flag context-copied Arabic phrasing as "unnatural" when it is not the generation model's own wording to judge.
- **Trust level:** Faithfulness/Relevance/Completeness scores in `answer_quality_raw.json` can be trusted directly. Language correctness scores for Arabic should be read with the caveat that ~15% may be overly harsh, specifically on answers that closely quote the retrieved context.
