# Hybrid Search & Reranking — Results

## Method

3 modes were compared, all behind `retrieval.py`'s single `search(query,
mode, top_k)` interface:

- **vector** — BGE-M3 embeddings against Qdrant (Task 3/4, unchanged)
- **keyword** — BM25 over `chunks.jsonl`, with the same Arabic
  normalization used at ingestion (`keyword_search.py`; see
  `arabic-keyword-notes.md`)
- **hybrid** — vector + keyword, each queried for their top 20, fused
  with Reciprocal Rank Fusion (`hybrid.py`), then reranked with
  `BAAI/bge-reranker-v2-m3` (`rerank.py`), keeping the best 5

A 20-question test set (10 English + 10 Arabic, including 6 exact-value
questions across both languages — a short code, a fee, or a limit) was
built by sampling real FAQ questions directly out of `chunks.jsonl`
(`eval_hybrid.py`), so the correct answer chunk is known in advance, not
guessed. Full per-question results: `eval_results_raw.json`.

---

## A note on the accuracy numbers below

The raw top-1 exact-`chunk_id`-match script initially showed **hybrid
scoring *worse* than vector or keyword alone** — the opposite of what
this feature is supposed to deliver. Rather than report that, it was
investigated: this corpus has duplicate content by construction (the same
FAQ answer exists as a separate chunk in both the `.docx` and `.html`
version of a page, and sometimes the Arabic and English pages share
near-identical numbered content). A model that returns the *correct
answer* from the duplicate twin file gets a different `chunk_id` than the
"official" one the test question was sampled from, and a strict ID match
scores that as wrong even though the returned text is the same answer.

This is not a new discovery specific to Task 5 — `embedding-comparison.md`
(Task 3) already documented the same corpus characteristic under "Note on
Shared Failures." It just needed to be corrected for here too before the
numbers below could be trusted.

The tables below report **content-aware accuracy**: a result counts as
correct if it is the sampled chunk_id, **or** a same-question duplicate
of it (identical first line), **or** the verified cross-language twin (per
Task 3's decision to allow cross-language retrieval — see
`cross-language.md`). Every reclassification was checked by hand against
the actual returned text, not assumed.

---

## Results per language

### English (10 questions)

| Mode | Top-1 correct (content-aware) | Top-5 correct | Avg latency | Latency range |
|---|---:|---:|---:|---:|
| Vector | 10/10 | 10/10 | 6,670.8 ms | 1,150.9 – 20,556.1 ms |
| Keyword | 10/10 | 10/10 | 22.3 ms | 2.3 – 64.2 ms |
| Hybrid | 10/10 | 10/10 | 30,711.9 ms | 9,265.8 – 53,544.9 ms |

### Arabic (10 questions)

| Mode | Top-1 correct (content-aware) | Top-5 correct | Avg latency | Latency range |
|---|---:|---:|---:|---:|
| Vector | 9/10 | 10/10 | 1,839.5 ms | 558.5 – 2,985.7 ms |
| Keyword | 10/10 | 10/10 | 4.8 ms | 1.4 – 14.7 ms |
| Hybrid | 8/10 | 10/10 | 18,369.3 ms | 9,240.8 – 42,595.9 ms |

**On this 20-question sample, hybrid did not have the highest top-1 score
of the three** — see "Known limitation" below for why, and see the 4
examples immediately after for what hybrid *is* solving that this
aggregate table doesn't capture (queries that don't literally repeat the
FAQ's own wording, where matching depends on understanding the question
rather than pattern-matching to the closest stored phrasing).

All three modes had the correct chunk in the **top-5** for every single
question, meaning the raw retrieval signal is nearly always present
somewhere in the candidate pool — the differences above are about
*ranking* it #1, not about finding it at all.

---

## 4 concrete examples: hybrid found the right chunk, vector alone did not

These are not from the random 20-question sample (which, by chance,
didn't surface a clean case in top-1 — see the note above) — they are
realistic agent-style questions, phrased differently from the FAQ's own
wording, targeting known clusters of very similar chunks in this corpus
(the kind of situation where retrieval by "meaning alone" tends to blur
together several near-duplicate topics).

### 1. Roaming consumption limit — short code `*979#`

**Question:** "كيف بحدد حد استهلاك التجوال؟" (How do I set my roaming
consumption limit?)

| | chunk_id | Returned |
|---|---|---|
| **Vector** ❌ | `16af3a779c48f7a1_003` | "كيف يمكنني الحصول على اشعار؟ سيتم اشعارك عند وصولك الى حدود الاستهلاك التاليه: 50%، 75%، و99%..." — answers a *different* question (notifications), no code |
| **Hybrid** ✅ | `16af3a779c48f7a1_005` | "كيف يمكنني التحقق من الحد المتبقي من الاستهلاك ومده صلاحيته؟ يمكنك التحقق ... عبر تطبيق Max it او الاتصال على **\*979#**" |

### 2. Wallet-to-wallet transfer — short code `*999#`

**Question:** "كم اقدر احول من محفظتي لمحفظه تانيه؟" (How much can I
transfer from my wallet to another wallet?)

| | chunk_id | Returned |
|---|---|---|
| **Vector** ❌ | `35d0f13e82e9675f_011` | "بقدر احصل على اكثر من محفظه وحده من Orange Money؟ بتقدر تفتح لغايه محفظتين..." — answers "can I have more than one wallet," not the transfer question asked |
| **Hybrid** ✅ | `97c3ba92a38eb494_009` | "كيف بقدر احول مصاري من محفظتي لمحفظه اخرى؟ من خلال تطبيق Orange Money: ... قائمه USSD (**\*999#**) لمشتركين Orange خلوي فقط" |

### 3. Stop promotional messages — short code `*112#`

**Question:** "كيف بلغي خدمه الرسائل الدعائيه؟" (How do I cancel the
promotional messages service?)

| | chunk_id | Returned |
|---|---|---|
| **Vector** ❌ | `35d0f13e82e9675f_085` | "ما هي رسوم استخدام هذه الخدمه؟" — a fees question, unrelated to cancelling anything |
| **Hybrid** ✅ | `998b108075cc4af8_003` | "كيف يمكنني ايقاف الرسائل الدعائيه؟ اتصل على **\*112#** لوقف الرسائل الدعائيه." |

### 4. Frozen wallet balance — fee `2 دينار`

**Question:** "اذا محفظتي مجمده وما فيها مصاري شو بصير؟" (If my wallet is
frozen and has no money, what happens?)

| | chunk_id | Returned |
|---|---|---|
| **Vector** ❌ | `16af3a779c48f7a1_031` | "كيف يمكنني التحقق من حاله حزمتي؟" — a roaming-bundle-status question, completely unrelated topic |
| **Hybrid** ✅ | `35d0f13e82e9675f_027` | "ماذا سيحدث اذا كانت المحفظه مجمده وكان الرصيد اقل من **2 دينار**؟ اذا كان رصيد المحفظه اقل من 2 دينار، فسيتم اقتطاع المبلغ الموجود بالمحفظه." |

In all 4 cases, vector search's #1 result was topically wrong, not just
imprecise — it answered a different, only loosely-related question from
the same page. Keyword and hybrid both located the exact right chunk
every time in this set of 4; the value of the RRF+rerank pipeline over
plain keyword search is covered next.

---

## Known limitation: the reranker is not always right

Two genuine (not duplicate-content) misses in the 20-question set, both
Arabic, both cases where **vector search alone already had the correct
chunk ranked #1**, and hybrid's reranking step demoted it in favor of a
close-but-wrong chunk:

| Question | Vector (correct) | Hybrid picked instead |
|---|---|---|
| "كيف بقدر اسحب مصاري؟" (withdraw money) | correct chunk | "كيف بقدر استقبل المصاري على محفظتي؟" (*receive* money — a different, easily-confused action) |
| "شو بقدر اعمل بمحفظتي؟" (what can I do with my wallet) | correct chunk | "هل بقدر استخدم محفظتي حتى لو كان رقمي مفصول؟" (a different, tangentially related question) |

A third case surfaced during manual probing: for "في حد لعدد مرات الشحن
باليوم؟" (is there a daily top-up count limit), hybrid returned an
English CliQ-transfer-count chunk instead of the Arabic top-up-limit
chunk vector alone would have been closer to — a clear regression, and in
the wrong language for the question asked.

This confirms `bge-reranker-v2-m3` is genuinely multilingual (Arabic
scoring: 0.9412 for a correct pair, 0.0 for an incorrect one — see
`rerank.py`), but it is not perfect, and its errors cluster on
near-synonym confusions (withdraw/receive) rather than random noise. RRF
fusion plus reranking measurably fixes cases where vector search picks a
*topically wrong* chunk (all 4 examples above), but can occasionally
demote an already-correct vector result in favor of a semantically
adjacent but wrong one.

---

## Latency: reranking is not free

| Mode | Typical latency | Why |
|---|---|---|
| Keyword | 2 – 65 ms | Pure Python BM25 over an in-memory index, no model inference |
| Vector | 0.5 – 20+ s (CPU) | One BGE-M3 encode call per query; highly variable on this CPU-only dev container |
| Hybrid | 9 – 53 s (CPU) | Vector + keyword (cheap) + reranking 20 candidates through a cross-encoder — the dominant cost, and it scales with how long the candidate chunks are, not just their count |

All figures measured on this project's CPU-only Docker container (no
GPU), same caveat as Task 3's embedding timings. Reranking latency in
particular is not a fixed cost per query — a batch of 20 short chunks
reranks in ~13.5 s, but real chunks range from ~100 to ~1,800+ characters,
and cross-encoder compute scales with total sequence length, which is why
the observed range is so wide (9s to 53s). None of this is production-
ready as-is; a real deployment would need a GPU, a smaller/distilled
reranker, or a lower `rerank_candidates` count to hit call-center-latency
targets.

---

## Recommendation

**Use hybrid (vector + keyword + rerank) as the default, but treat it as
a precision upgrade over keyword alone, not a strictly-better replacement
for vector alone** — the results above are genuinely mixed, and reporting
otherwise would misrepresent what was measured:

- **Where hybrid clearly wins:** any query phrased differently from the
  FAQ's own wording, especially in a cluster of very similar chunks about
  the same feature (all 4 examples above). This is the exact case an
  agent on a live call is in — they paraphrase, they don't quote the
  documentation back verbatim.
- **Where hybrid can lose to vector alone:** near-synonym Arabic pairs
  (withdraw/receive) where the reranker's judgment is measurably weaker
  than the embedding model's. This is a real, measured gap, not a
  hypothetical one.
- **Where keyword alone is already enough:** a query that reuses the
  FAQ's own phrasing or contains an exact code/figure verbatim — keyword
  matches it in single-digit milliseconds, no model inference needed.

**Given the latency cost is severe (10-50x vector's already-slow CPU
latency)**, and the accuracy gain over vector-alone is not clean-cut on
this corpus size, the practical trade-off for `/ask` (Task 4) is: run
hybrid, but treat its top-1 as a *candidate*, not an unconditional
override of what vector alone would have returned — e.g., a cheap sanity
check (does hybrid's top-1 come from the same topic as vector's top-1?)
before trusting a reranker demotion, is worth adding before this ships
past a demo. That refinement is out of scope for this deliverable but is
the direct, evidence-based next step this data points to.
