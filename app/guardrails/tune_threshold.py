"""
Task 6 -- Derives the per-language relevance thresholds used by
guardrails.passes_relevance_threshold() and reports the numbers behind
them into threshold-tuning.md.

Method: run a set of POSITIVE queries (real, answerable questions sampled
from chunks.jsonl the same way Task 5's eval_hybrid.py did -- the correct
chunk is known in advance) and a set of NEGATIVE queries (genuinely
unanswerable from this corpus: either clearly out-of-domain, or
telecom-adjacent but not covered by these 7 topic pages) through hybrid
search (the /ask default mode), and record each one's top-1 rerank_score.

The threshold for a language is picked as the midpoint between the worst
(minimum) positive score and the best (maximum) negative score for that
language -- i.e. the value that would have correctly separated every
positive from every negative in this measurement, not an arbitrary
constant. If the two distributions overlap (no such value exists), that
is reported explicitly rather than papered over with a threshold that
looks clean but wasn't actually validated by the data.
"""

from app.retrieval.retrieval import hybrid_search
from app.retrieval.eval_hybrid import build_test_set

# Genuinely unanswerable from this 7-topic-page corpus (mobile-lines,
# fiber-adsl, orange-money, international-roaming, bills-payment,
# short-codes, help-center) -- a mix of clearly out-of-domain questions
# and telecom-adjacent-but-uncovered ones, so the threshold isn't tuned
# only against the "easy" unrelated case.
NEGATIVE_QUERIES = {
    "en": [
        "What's the weather like in Amman today?",
        "What is the capital of Jordan?",
        "Can you help me write a Python script?",
        "What is Orange's current stock price?",
        "How do I reset my email password?",
        "What's the best restaurant in Amman?",
        "Tell me a joke.",
        "What is 15% of 200?",
        "Can I get a discounted family postpaid bundle?",
        "Do you sell smartphones directly in your stores?",
    ],
    "ar": [
        "شو الطقس بعمان اليوم؟",
        "شو عاصمة الاردن؟",
        "ممكن تكتبلي كود بايثون؟",
        "شو سعر سهم اورنج حاليا؟",
        "كيف بغير كلمة سر الايميل تبعي؟",
        "وين أحسن مطعم بعمان؟",
        "احكيلي نكتة",
        "كم ناتج 15% من 200؟",
        "في عندكم باقة عائلية مخفضة للاشتراك الشهري؟",
        "بتبيعوا موبايلات مباشرة من المحلات؟",
    ],
}


def collect_scores(queries: list[str]) -> list[float]:
    scores = []
    for q in queries:
        results = hybrid_search(q, top_k=5)
        score = results[0]["rerank_score"] if results else float("-inf")
        scores.append(score)
        print(f"  [negative] score={score:.4f}  {q[:60]}")
    return scores


def run() -> dict:
    positive_set = build_test_set()  # Task 5's 20-question set (10 en, 10 ar)

    positive_scores = {"en": [], "ar": []}
    print(f"--- Positive queries ({len(positive_set)}) ---")
    for i, item in enumerate(positive_set, 1):
        results = hybrid_search(item["question"], top_k=5)
        score = results[0]["rerank_score"] if results else float("-inf")
        positive_scores[item["language"]].append(
            {"question": item["question"], "score": score}
        )
        print(f"  [{i}/{len(positive_set)}][positive] score={score:.4f}  {item['question'][:60]}")

    negative_scores = {}
    for lang, queries in NEGATIVE_QUERIES.items():
        print(f"\n--- Negative queries ({lang}, {len(queries)}) ---")
        scores = collect_scores(queries)
        negative_scores[lang] = [
            {"question": q, "score": s} for q, s in zip(queries, scores)
        ]

    thresholds = {}
    report = {}
    for lang in ["en", "ar"]:
        pos_vals = [item["score"] for item in positive_scores[lang]]
        neg_vals = [item["score"] for item in negative_scores[lang]]
        min_pos = min(pos_vals)
        max_neg = max(neg_vals)
        clean_separation = min_pos > max_neg
        threshold = (min_pos + max_neg) / 2

        thresholds[lang] = round(threshold, 4)
        report[lang] = {
            "min_positive": round(min_pos, 4),
            "max_negative": round(max_neg, 4),
            "avg_positive": round(sum(pos_vals) / len(pos_vals), 4),
            "avg_negative": round(sum(neg_vals) / len(neg_vals), 4),
            "clean_separation": clean_separation,
            "threshold": round(threshold, 4),
        }

    return {
        "thresholds": thresholds,
        "report": report,
        "positive_scores": positive_scores,
        "negative_scores": negative_scores,
    }


def write_markdown(outcome: dict, path: str = "app/guardrails/threshold-tuning.md") -> None:
    lines = [
        "# Relevance Threshold Tuning",
        "",
        "## Method",
        "",
        "Ran the 20-question positive set from Task 5's `eval_hybrid.py` "
        "(10 English + 10 Arabic, real questions sampled from `chunks.jsonl` "
        "with a known correct answer) plus 10 negative questions per "
        "language (genuinely unanswerable from this 7-topic-page corpus -- "
        "either clearly out-of-domain or telecom-adjacent but not covered) "
        "through `hybrid_search` (the `/ask` default mode), and recorded "
        "each query's top-1 `rerank_score`.",
        "",
        "The threshold per language is the midpoint between the worst "
        "(minimum) positive score and the best (maximum) negative score -- "
        "the value this measurement says would have separated every "
        "positive from every negative, not an arbitrary constant.",
        "",
        "---",
        "",
        "## Results",
        "",
        "| Language | Min positive score | Max negative score | Avg positive | Avg negative | Clean separation? | Threshold set |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for lang in ["en", "ar"]:
        r = outcome["report"][lang]
        lines.append(
            f"| {lang} | {r['min_positive']} | {r['max_negative']} | "
            f"{r['avg_positive']} | {r['avg_negative']} | "
            f"{'yes' if r['clean_separation'] else '**no -- overlap**'} | "
            f"{r['threshold']} |"
        )

    lines += ["", "---", "", "## Per-query scores", ""]
    for lang in ["en", "ar"]:
        lines.append(f"### {lang.upper()} -- positive (answerable) queries")
        lines.append("")
        for item in outcome["positive_scores"][lang]:
            lines.append(f"- `{item['score']:.4f}` — {item['question']}")
        lines.append("")
        lines.append(f"### {lang.upper()} -- negative (unanswerable) queries")
        lines.append("")
        for item in outcome["negative_scores"][lang]:
            lines.append(f"- `{item['score']:.4f}` — {item['question']}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[SAVED] {path}")


if __name__ == "__main__":
    outcome = run()
    for lang, r in outcome["report"].items():
        print(f"[{lang}] min_pos={r['min_positive']} max_neg={r['max_negative']} "
              f"clean={r['clean_separation']} threshold={r['threshold']}")
    write_markdown(outcome)
