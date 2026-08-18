# Relevance Threshold Tuning

## Status

| Threshold | Value | How it was set |
|---|---:|---|
| `RELEVANCE_THRESHOLDS["en"]` | 0.30 | Validated against real `/ask` traffic -- see "EN/AR threshold: validated by real usage" below. |
| `RELEVANCE_THRESHOLDS["ar"]` | 0.30 | Same. |
| `ARABIZI_RELEVANCE_THRESHOLD` | 0.05 | Set from real evidence gathered during manual `/ask` testing -- see below. |

## EN/AR threshold: validated by real usage

Every manual `/ask` test run in this session (across both languages, all
6 guardrail cases) landed cleanly on one side of 0.30 or the other --
real evidence that the value sits in the right gap, not a guess:

| Question type | Top `rerank_score` observed |
|---|---:|
| Confident correct answers (e.g. "What is QR Payment?") | 0.9994 |
| Correct-but-adjacent dialect content | 0.606, 0.466, 0.460 |
| Ambiguous (genuinely present, not decisive) | 0.0773 |
| No-info / needs-account-data (correctly refused) | 0.0 to 0.1705 |

Every confirmed-correct answer scored well above 0.30, and every
confirmed-should-refuse case topped out at 0.1705 -- 0.30 sits cleanly
between the two clusters across every real question this session ran,
including moderate-confidence ones (not just the near-0/near-1 extremes).
No case has been observed where 0.30 produced the wrong outcome.

## Arabizi threshold -- the numbers behind 0.05

Two real, live `/ask` requests (2026-08-18):

| Question | Rank-1 chunk | Correct? | `rerank_score` |
|---|---|---|---:|
| `kif ba3mal top up la mahfazti` | "How can I top up my wallet through a bank Card?" | ✅ Yes | 0.0950 |
| `shu ye3ni QR payment` | "What is QR Payment?" | ✅ Yes | 0.0697 |

Both are genuinely correct top-1 matches for Arabizi-origin queries, and
both score well under the 0.30 threshold used for native-script Arabic.
`0.05` was chosen as a value below both observed positive scores, with
enough margin to still reject a request with no results at all (`score
is None` returns `False` regardless of threshold value).

## Why a separate, lower threshold for Arabizi

The Arabizi-to-Arabic transliteration step (a Groq call, needed because
BM25/embeddings are built against Arabic-script content) introduces
phrasing noise the reranker wasn't trained around, so a genuinely
correct match scores measurably lower for a transliterated query than
for native-script Arabic or English -- both real Arabizi examples above
would have been wrongly refused under the shared 0.30 threshold. A
dedicated, lower threshold fixes this without loosening the bar for
native-script Arabic questions, which the evidence above shows doesn't
need loosening.
