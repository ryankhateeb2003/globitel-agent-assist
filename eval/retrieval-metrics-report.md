# Retrieval Metrics Report

## Method

Every non-`should_refuse` item in `eval/dataset_v1.json` (72 of 80 -- `should_refuse` items have no correct chunk to rank, by design) was run through `app/retrieval/retrieval.py`'s `search()` in **hybrid** mode (the `/ask` default), at `top_k=10`, using the customer's raw question wording -- **without** the LLM query-normalization step `/ask` applies in production, to measure the retrieval algorithm's own baseline capability first.

`multi_chunk` items have two correct chunk ids; hit@k counts a hit if EITHER is found in the top k, recall@k is the fraction of the two found.

---

## Overall, by language

| Language | n | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Precision@1 | Precision@3 | Precision@5 | Precision@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 32 | 0.906 | 0.81 | 1.00 | 1.00 | 1.00 | 0.75 | 0.97 | 1.00 | 1.00 | 0.81 | 0.40 | 0.25 | 0.13 |
| ar | 32 | 0.839 | 0.75 | 0.94 | 0.94 | 0.94 | 0.66 | 0.88 | 0.92 | 0.94 | 0.75 | 0.35 | 0.23 | 0.12 |

---

## By type and language

| Type_Language | n | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Precision@1 | Precision@3 | Precision@5 | Precision@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exact_value_en | 8 | 0.875 | 0.75 | 1.00 | 1.00 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 0.75 | 0.33 | 0.20 | 0.10 |
| simple_factual_en | 12 | 1.000 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 0.10 |
| exact_value_ar | 8 | 0.729 | 0.62 | 0.88 | 0.88 | 0.88 | 0.62 | 0.88 | 0.88 | 0.88 | 0.62 | 0.29 | 0.17 | 0.09 |
| simple_factual_ar | 12 | 0.917 | 0.83 | 1.00 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 0.83 | 0.33 | 0.20 | 0.10 |
| multi_chunk_en | 8 | 0.750 | 0.50 | 1.00 | 1.00 | 1.00 | 0.25 | 0.88 | 1.00 | 1.00 | 0.50 | 0.58 | 0.40 | 0.20 |
| multi_chunk_ar | 8 | 0.875 | 0.75 | 1.00 | 1.00 | 1.00 | 0.38 | 0.75 | 0.94 | 1.00 | 0.75 | 0.50 | 0.38 | 0.20 |
| dialect_arabizi_ar | 4 | 0.750 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.75 | 0.25 | 0.15 | 0.08 |
| informal_en | 4 | 1.000 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 0.10 |

---

## Matched pairs -- same question, EN vs AR, side by side

Each pair points at the identical FAQ entry in both languages (`eval/matched_pairs.json`). Scored here by re-running retrieval directly on each pair's question text (these are not necessarily the same items already scored above, since matched_pairs.json was built independently -- see eval/README.md).

| Pair | Topic | EN Hit@5 | AR Hit@5 | EN rank | AR rank |
|---|---|---:|---:|---:|---:|
| pair-001 | bills-payment | yes | yes | 1 | 1 |
| pair-002 | bills-payment | yes | yes | 1 | 1 |
| pair-003 | bills-payment | yes | yes | 1 | 1 |
| pair-004 | bills-payment | yes | yes | 1 | 1 |
| pair-005 | bills-payment | yes | yes | 1 | 1 |
| pair-006 | bills-payment | yes | yes | 1 | 1 |
| pair-007 | bills-payment | yes | yes | 1 | 1 |
| pair-008 | bills-payment | yes | yes | 1 | 1 |
| pair-009 | bills-payment | yes | yes | 1 | 1 |
| pair-010 | bills-payment | yes | yes | 1 | 1 |
| pair-011 | bills-payment | yes | yes | 1 | 1 |
| pair-012 | fiber-adsl | yes | yes | 1 | 1 |
| pair-013 | fiber-adsl | yes | yes | 1 | 3 |
| pair-014 | fiber-adsl | yes | yes | 1 | 1 |
| pair-015 | fiber-adsl | yes | yes | 1 | 1 |
| pair-016 | fiber-adsl | yes | yes | 1 | 1 |
| pair-017 | fiber-adsl | yes | yes | 1 | 1 |
| pair-018 | fiber-adsl | yes | yes | 1 | 1 |
| pair-019 | fiber-adsl | yes | yes | 1 | 1 |
| pair-020 | fiber-adsl | yes | yes | 1 | 1 |

**0/20 matched pairs disagree between languages on Hit@5** (one language found the identical FAQ entry, the other didn't) -- on identical questions, that gap is attributable to the language itself, not question difficulty.

---

## 10 worst questions

- **ar-dialect-001** (ar/dialect_arabizi, MRR=0.00) -- "kif ba2dar atchek 3ala el package w shu ba2i minha?" -- correct chunk found at rank not in top 10
- **ar-shortcode-003** (ar/exact_value, MRR=0.00) -- "شو الكود يلي بعرفني على رصيدي والحزم المتبقية؟" -- correct chunk found at rank not in top 10
- **ar-shortcode-002** (ar/exact_value, MRR=0.33) -- "كيف بفعّل ميزة تنبيه المكالمات الفائتة؟" -- correct chunk found at rank 3
- **en-exact-008** (en/exact_value, MRR=0.50) -- "How do I transfer money from my wallet to another mobile wallet?" -- correct chunk found at rank 2
- **ar-exact-008** (ar/exact_value, MRR=0.50) -- "كيف بقدر احول مصاري من محفظتي لمحفظه اخرى؟" -- correct chunk found at rank 2
- **ar-simple-013** (ar/simple_factual, MRR=0.50) -- "كم مده صلاحيه القسائم الالكترونيه ؟" -- correct chunk found at rank 2
- **ar-simple-020** (ar/simple_factual, MRR=0.50) -- "كيف يمكنني التحقق من حاله سقف استهلاك و صلاحيته؟" -- correct chunk found at rank 2
- **en-multi-004** (en/multi_chunk, MRR=0.50) -- "To Which countries can I send and receive money and how much money can I Send an" -- correct chunk found at rank 2
- **en-multi-005** (en/multi_chunk, MRR=0.50) -- "How to use QR and where Can I use QR?" -- correct chunk found at rank 2
- **en-multi-007** (en/multi_chunk, MRR=0.50) -- "How can I send an SMS while roaming and how can I use internet while roaming?" -- correct chunk found at rank 2

---

## Weakest language + type combination

**dialect_arabizi_ar** -- Hit@5 = 0.75, MRR = 0.750 (n=4). This is the exact cell to prioritize in Task 4's experiments.