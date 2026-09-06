# Relevance Threshold Tuning

## Outcome: rrf_score rejected as a confidence signal

The measurement below is the evidence that led to a design change, not
the adopted configuration. It shows positive (answerable) and negative
(out-of-scope) queries scoring almost identically on `rrf_score` --
Arabic's minimum-positive and maximum-negative are literally the same
number (0.0320), and English's gap (0.0325 vs 0.0323) is too thin to
trust. This isn't a tuning failure to fix with a different threshold
value -- RRF's score is a function of *rank position*
(`1/(k+rank)`), not match strength, so a totally unrelated question's
"closest available" chunk scores nearly as high as a genuinely relevant
one's, since both simply rank #1 in the fusion.

**What is actually used instead:** `guardrails.RELEVANCE_THRESHOLDS`
(0.30 for both languages) compared against a plain `vector_search()`
score computed separately for this purpose -- see
`guardrails.passes_relevance_threshold()`'s docstring and
`app/api/main.py`'s `confidence_score` computation. That threshold was
never rrf_score-based and did not need re-tuning; this file exists to
record why the rrf_score alternative was tried and rejected, for anyone
revisiting this decision later.

---

## Method (as originally run, against rrf_score)

Ran the 20-question positive set from Task 5's `eval_hybrid.py` (10 English + 10 Arabic, real questions sampled from `chunks.jsonl` with a known correct answer) plus 10 negative questions per language (genuinely unanswerable from this 7-topic-page corpus -- either clearly out-of-domain or telecom-adjacent but not covered) through `hybrid_search` (the `/ask` default mode, use_rerank=False), and recorded each query's top-1 `rrf_score`.

The threshold per language is the midpoint between the worst (minimum) positive score and the best (maximum) negative score -- the value this measurement says would have separated every positive from every negative, not an arbitrary constant.

---

## Results

| Language | Min positive score | Max negative score | Avg positive | Avg negative | Clean separation? | Threshold set |
|---|---:|---:|---:|---:|---|---:|
| en | 0.0325 | 0.0323 | 0.0327 | 0.0272 | yes | 0.0324 |
| ar | 0.032 | 0.032 | 0.0326 | 0.022 | **no -- overlap** | 0.032 |

---

## Per-query scores

### EN -- positive (answerable) queries

- `0.0328` — 1) How can I subscribe to Arabia Passenger Bundles?
- `0.0328` — What are Orange ADSL features ?
- `0.0325` — How do I transfer money from my wallet to another mobile wallet?
- `0.0328` — Do I need a bank account to use Orange Money?
- `0.0328` — Data carry over feature?
- `0.0328` — What is the available speeds for the ADSL offers?
- `0.0325` — How Can I create new Alias?
- `0.0328` — Can I use a security system alarm with the Digital Voice service?
- `0.0325` — Can I use my wallet if my phone number is disconnected?
- `0.0325` — How to use the CliQ service?

### EN -- negative (unanswerable) queries

- `0.0285` — What's the weather like in Amman today?
- `0.0301` — What is the capital of Jordan?
- `0.0164` — Can you help me write a Python script?
- `0.0164` — What is Orange's current stock price?
- `0.0323` — How do I reset my email password?
- `0.0313` — What's the best restaurant in Amman?
- `0.0270` — Tell me a joke.
- `0.0267` — What is 15% of 200?
- `0.0313` — Can I get a discounted family postpaid bundle?
- `0.0320` — Do you sell smartphones directly in your stores?

### AR -- positive (answerable) queries

- `0.0325` — ما هي رسوم استخدام هذه الخدمه؟
- `0.0328` — هل توجد اي رسوم ل Orange Money لاضافه بطاقتي الى Google Pay؟
- `0.0328` — ما هي ميزه التحكم في فاتوره بيانات التجوال (حمايه من ارتفاع الفواتير)؟
- `0.0325` — كيف بقدر اسحب مصاري؟
- `0.0320` — اين يمكنني استخدام Google Pay؟
- `0.0328` — ماذا علي ان افعل للوصول الى الفاتوره التفصيليه على الانترنت؟
- `0.0325` — كيف يمكنني التاكد من انه تم اجراء دفعه ؟
- `0.0328` — هل يمكنني استخدام تنبيه نظام الامان مع خدمه الاتصال الصوتي الرقمي؟
- `0.0328` — ما هي ميزه ترحيل حزم الانترنت؟
- `0.0328` — شو بقدر اعمل بمحفظتي؟

### AR -- negative (unanswerable) queries

- `0.0164` — شو الطقس بعمان اليوم؟
- `0.0315` — شو عاصمة الاردن؟
- `0.0164` — ممكن تكتبلي كود بايثون؟
- `0.0164` — شو سعر سهم اورنج حاليا؟
- `0.0310` — كيف بغير كلمة سر الايميل تبعي؟
- `0.0164` — وين أحسن مطعم بعمان؟
- `0.0164` — احكيلي نكتة
- `0.0164` — كم ناتج 15% من 200؟
- `0.0271` — في عندكم باقة عائلية مخفضة للاشتراك الشهري؟
- `0.0320` — بتبيعوا موبايلات مباشرة من المحلات؟
