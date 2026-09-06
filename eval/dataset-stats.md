# Dataset Statistics -- eval/dataset_v1.json

**Total items:** 80
**Matched pairs:** 20/20

## Counts per type, per language

| Type | English | Arabic |
|---|---:|---:|
| dialect_arabizi | 0 | 4 |
| exact_value | 8 | 8 |
| informal | 4 | 0 |
| multi_chunk | 8 | 8 |
| should_refuse | 8 | 8 |
| simple_factual | 12 | 12 |

## Coverage across source pages (topics)

| Topic | Items sampled from it |
|---|---:|
| mobile-lines | 6 |
| fiber-adsl | 13 |
| orange-money | 16 |
| international-roaming | 15 |
| bills-payment | 8 |
| short-codes | 6 |
| help-center | 0 |

## Blind spots

**Topics with zero sampled items:** help-center -- retrieval/answer-quality metrics in Task 2/3 will have no signal at all for these pages; either they had no clean question-line chunks to sample from, or random sampling simply didn't pick one. Worth a manual top-up pass before treating Task 2's per-topic numbers as complete.

`should_refuse` items intentionally have `expected_answer: null`, `source_file: null` -- 
there is no correct chunk for them by design; the correct system behavior is refusal itself.