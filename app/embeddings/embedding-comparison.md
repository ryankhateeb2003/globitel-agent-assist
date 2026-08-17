# Embedding Model Comparison

## Objective
Compare 3 embedding model types on the same bilingual (Arabic/English) content, 
to determine which is usable for this product. The hosted-API paid baseline was 
excluded from this comparison — no API key/budget available for this phase — so 
the comparison is limited to the two local, free models below. This is a 
deliberate scope decision, not an oversight.

---

## Models Compared

| Model | Type | Dimension | Purpose |
|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | English-focused | 384 | Establish that an English-only model fails or degrades on Arabic |
| `BAAI/bge-m3` | Multilingual | 1024 | The realistic choice for a bilingual product |

---

## Embedding Time & Cost (full corpus, 625 chunks, CPU only)

| Model | Total time | Chunks/second |
|---|---|---|
| MiniLM (English-only) | 25.48 s | 24.53 |
| BGE-M3 (Multilingual) | 956.67 s (~16 min) | 0.65 |

**Observation:** BGE-M3 is ~37x slower than MiniLM to embed the same corpus on 
CPU. This is a real cost/latency trade-off, not a marginal difference — it 
matters directly for the re-indexing/update path (Task 3) and for any future 
real-time embedding needs.

---

## Retrieval Quality: 20 Test Queries (10 English + 10 Arabic)

Queries were sampled directly from real FAQ questions already present in the 
corpus (`chunks.jsonl`), so the correct answer chunk is known in advance. A 
result counts as "correct" only if the model's top-1 retrieved chunk exactly 
matches the source chunk the question came from.

### Overall accuracy (top-1 correct chunk retrieved)

| Model | Correct | Total | Accuracy |
|---|---|---|---|
| MiniLM (English-only) | 8 | 20 | 40.0% |
| BGE-M3 (Multilingual) | 12 | 20 | 60.0% |

### Accuracy broken down by language

| Model | English accuracy | Arabic accuracy |
|---|---|---|
| MiniLM (English-only) | 7/10 = **70%** | 1/10 = **10%** |
| BGE-M3 (Multilingual) | 6/10 = **60%** | 6/10 = **60%** |

**This is the key finding.** On English queries, the two models perform 
similarly (MiniLM even slightly ahead, as expected for an English-tuned model). 
On Arabic queries, MiniLM's accuracy collapses from 70% to 10%, while BGE-M3 
holds steady at ~60% across both languages.

---

## Concrete Failure Example: Confident Wrong Answers

The clearest evidence is not just that MiniLM scores lower — it's that MiniLM 
returns **high similarity scores for wrong results** on Arabic, which is worse 
than simply failing, because a high score looks trustworthy.

**Query (Arabic):** "كيف بقدر افتح محفظة اورنج موني؟" (How do I open an Orange 
Money wallet?)

| Model | Score | Result returned |
|---|---|---|
| MiniLM | **0.86** (high) | "كيف يمكنني التحقق من حالة حزمتي؟" — unrelated (about checking bundle status) |
| BGE-M3 | 0.71 (lower) | "كيف بقدر افتح محفظة Orange Money؟ هلا صار بإمكانك..." — **the correct answer** |

MiniLM assigns its *highest* confidence to a *wrong* answer. This is because it 
measures surface-level character/shape similarity in Arabic script, not 
semantic meaning — it was never trained to understand Arabic. BGE-M3, trained 
on Arabic, correctly identifies the matching content despite a numerically 
lower score. A raw similarity score from an unsupported-language model is not 
a reliable confidence signal.

---

## Note on Shared Failures (Both Models Wrong)

A handful of queries (5, 8, 10, 19, 20 in the test run) failed for **both** 
models. On inspection, this is not a language-support issue — it's near-duplicate 
FAQ content in the source corpus itself (e.g. two separate chunks answering 
"هل سيتوقف الاقتطاع اذا قمت بتنشيط محفظتي؟" with near-identical phrasing). Both 
models retrieved a semantically valid but differently-ID'd chunk. This is a 
content-quality issue for the corpus/chunking stage, not an embedding model 
weakness, and is noted here for completeness rather than counted against 
either model.

---

## Answer to Review Question 1
**"Why does an English only embedding model fail on this corpus, and what is 
your evidence?"**

An English-only model (MiniLM) fails on Arabic because it was never trained on 
Arabic text and therefore cannot represent Arabic semantics — only superficial 
character patterns. The evidence: on identical FAQ-derived test questions, its 
top-1 retrieval accuracy dropped from 70% (English) to 10% (Arabic), and in 
several cases it assigned its *highest* confidence scores to *incorrect* 
results, which is more dangerous than a low-confidence failure for a product 
where an agent reads the answer aloud to a customer.

---

## Conclusion

**BAAI/bge-m3 is the model selected for this product.** It is ~37x slower to 
embed than MiniLM, but this cost is a one-time (or incremental, via the update 
path) indexing cost, not a per-query cost — and it is the only one of the two 
models that provides usable retrieval accuracy on Arabic content, which is a 
hard requirement for this product (Jordan/Saudi/UAE contact centers, Arabic 
customers).