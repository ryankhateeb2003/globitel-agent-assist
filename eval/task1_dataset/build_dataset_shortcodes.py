"""
Part Two, Task 1 -- manual top-up for the `short-codes` topic.

short-codes.html isn't structured as question-per-line FAQs like the
other 6 corpus pages (see eval/task1_dataset/README.md's coverage note) -- it's a
flat list of "code / what it does" lines with no "?" anywhere, so
build_dataset.py's extract_question() finds nothing there at all. These
3 items per language are hand-written questions whose answer is copied
verbatim from the real short-codes.html chunk (chunk_id
60409545ab124892_000 / 9044d8dde9894bc6_000) -- not fabricated content,
just an authored question for content the page never phrases as one.

help-center.html is NOT topped up here -- inspected by hand, it is a
pure navigation menu (page section titles like "FAQs", "Find Shops",
"Opening hours") with zero actual answerable content, so there is
genuinely nothing to write a real question against. That is reported
as-is in dataset-stats.md rather than papered over.

Usage: python eval/task1_dataset/build_dataset_shortcodes.py (run after build_dataset_part2.py)
"""

import json
from pathlib import Path

SHORT_CODES_ITEMS = [
    {
        "language": "en", "type": "exact_value", "difficulty": "easy",
        "question": "What code do I dial for SOS (emergency) credit?",
        "expected_answer": "Press *606# for SOS credit (emergency credit) service.",
        "_chunk_id": "9044d8dde9894bc6_000",
    },
    {
        "language": "en", "type": "exact_value", "difficulty": "easy",
        "question": "How do I activate Missed Call Alert (MCA)?",
        "expected_answer": "Press *130# for “ Missed call Alert (MCA)” service.",
        "_chunk_id": "9044d8dde9894bc6_000",
    },
    {
        "language": "en", "type": "exact_value", "difficulty": "easy",
        "question": "What short code do I use to check my balance and remaining bundles?",
        "expected_answer": "Press *155# to check your balance and remaining bundles.",
        "_chunk_id": "9044d8dde9894bc6_000",
    },
    {
        "language": "ar", "type": "exact_value", "difficulty": "easy",
        "question": "شو الكود يلي بضغطه لرصيد الطوارئ؟",
        "expected_answer": "لرصيد الطوارىء اضغط *606#",
        "_chunk_id": "60409545ab124892_000",
    },
    {
        "language": "ar", "type": "exact_value", "difficulty": "easy",
        "question": "كيف بفعّل ميزة تنبيه المكالمات الفائتة؟",
        "expected_answer": "لميزه تنبيه المكالمات الفائته اضغط *130#",
        "_chunk_id": "60409545ab124892_000",
    },
    {
        "language": "ar", "type": "exact_value", "difficulty": "easy",
        "question": "شو الكود يلي بعرفني على رصيدي والحزم المتبقية؟",
        "expected_answer": "لمعرفه الرصيد والحزم المتبقيه اضغط *155#",
        "_chunk_id": "60409545ab124892_000",
    },
]


def main():
    dataset_path = Path("eval/task1_dataset/dataset_v1.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    counter = {"en": 0, "ar": 0}
    added = []
    for raw in SHORT_CODES_ITEMS:
        lang = raw["language"]
        counter[lang] += 1
        source_file = "corpus/en/short-codes.html" if lang == "en" else "corpus/ar/short-codes.html"
        added.append({
            "id": f"{lang}-shortcode-{counter[lang]:03d}",
            "question": raw["question"],
            "expected_answer": raw["expected_answer"],
            "source_file": source_file,
            "source_section": "Helpful short codes" if lang == "en" else "رموز قصيره مفيده",
            "language": lang,
            "type": raw["type"],
            "difficulty": raw["difficulty"],
            "_chunk_id": raw["_chunk_id"],
            "_topic": "short-codes",
        })

    # Keep exact_value at exactly N_EXACT_VALUE_PER_LANG (8) per the PDF's
    # spec -- adding short-codes items would otherwise push it to 11/lang.
    # Remove the surplus from whichever OTHER topic has the most
    # exact_value items per language (currently orange-money, by far the
    # largest source page) rather than a random one, so the trade-off is
    # "least representative single-page loss" not arbitrary.
    for lang in ["en", "ar"]:
        n_new = sum(1 for a in added if a["language"] == lang)
        exact_items = [d for d in dataset if d["language"] == lang and d["type"] == "exact_value"]
        by_topic = {}
        for it in exact_items:
            by_topic.setdefault(it["_topic"], []).append(it)

        # Remove from the largest topic(s) first, repeatedly, until n_new
        # slots are freed -- a single topic may not have enough surplus
        # on its own once stratified sampling already balanced them.
        to_remove = []
        while len(to_remove) < n_new:
            surplus_topic = max(by_topic, key=lambda t: len(by_topic[t]))
            if not by_topic[surplus_topic]:
                break
            to_remove.append(by_topic[surplus_topic].pop())

        for it in to_remove:
            dataset.remove(it)
        print(f"[{lang}] removed {len(to_remove)} exact_value item(s) "
              f"to make room for {n_new} short-codes item(s), keeping the {lang} exact_value "
              f"quota at {len(exact_items) - len(to_remove) + n_new}")

    dataset.extend(added)
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ADDED] {len(added)} short-codes items -- {len(dataset)} total now")


if __name__ == "__main__":
    main()
