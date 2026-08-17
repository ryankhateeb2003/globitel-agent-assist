# Cross-Language Retrieval

## Objective
Test whether an Arabic query retrieves the English document holding the same 
answer (and vice versa), and decide whether this cross-language behaviour is 
desirable or should be filtered out by language.

Only `bge_m3` was tested here — `minilm_en` is already established 
(`embedding-comparison.md`) as effectively non-functional on Arabic, so its 
cross-language behaviour is not a meaningful product question.

---

## Method
4 queries were run (2 Arabic, 2 English), each with a known matching FAQ entry 
that exists in **both** languages in the corpus. For each query, the top-5 
results were inspected for hits in the *other* language.

---

## Results

| # | Query language | Query | Cross-language hits (top-5) | Best cross-language score |
|---|---|---|---|---|
| 1 | Arabic | "كيف بقدر افتح محفظة اورنج موني؟" | 2/5 | 0.6706 (EN) |
| 2 | English | "How do I open an Orange Money wallet?" | 1/5 | 0.7447 (AR) |
| 3 | Arabic | "شو هي رسوم استخدام الخدمة؟" | 3/5 | 0.8632 (EN) |
| 4 | English | "What are the fees for using this service?" | 2/5 | 0.9415 (AR) |

In every single test, the correct same-topic chunk in the *other* language 
appeared in the top-5 results, at a score close to (sometimes nearly equal to) 
the same-language top result. This is not incidental noise — it is a 
consistent, repeatable behaviour of the model.

---

## Finding
**BGE-M3 retrieves semantically equivalent content across Arabic and English 
reliably.** It is not simply matching surface text; it is placing 
translation-equivalent sentences close together in vector space regardless of 
script. This is expected behaviour for a model explicitly trained for 
multilingual/cross-lingual retrieval.

---

## Decision: Allow cross-language retrieval, do not filter by language

**We chose NOT to filter search results by query language.**

### Reasoning
1. **Product fit**: this is an agent-assist tool for contact center agents, not 
   an end-customer chat product. An agent may ask a question in Arabic while 
   the only correctly-worded documentation happens to sit in the English 
   source page (or vice versa) — filtering would hide a valid, correct answer 
   from the agent for no real benefit.
2. **The English and Arabic FAQ pages are translations of the same source 
   content** (per Task 1's corpus structure: every `/en/` page has an `/ar/` 
   twin). Cross-language hits are therefore not "wrong-language noise" — they 
   are duplicate answers to the same question, which is useful redundancy, not 
   a failure mode.
3. **Downstream language handling is done at the answer stage, not the 
   retrieval stage**: Task 4's `/ask` endpoint is responsible for detecting the 
   query language and instructing the model to *answer* in that language, 
   regardless of which language the retrieved source chunk was written in. 
   Filtering retrieval by language would solve a problem that doesn't need 
   solving here, and would silently reduce recall (fewer chunks available to 
   answer from) for no measured benefit.

### When this decision would need revisiting
If a future evaluation shows the answer-generation model quotes or leaks 
source-language text into a differently-languaged answer (e.g. an Arabic 
answer accidentally containing an English sentence copied from a retrieved 
English chunk), that would be a reason to either filter by language at 
retrieval time or add an explicit instruction/guard at the prompt level 
(Task 4) instead. This has not been observed yet since Task 4 (the `/ask` 
endpoint) is not built at this stage.