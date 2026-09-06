"""
Part Two, Task 1 -- extends eval/dataset_v1.json (built by build_dataset.py)
with the 3 categories that can't be pulled straight out of the corpus by
a simple sampler: multi_chunk, should_refuse, dialect/Arabizi.

multi_chunk: pairs of adjacent same-topic chunks, combined into one
question whose answer is the concatenation of both real chunks' text --
grounded in real corpus content, not invented, but the *combination* is
authored rather than found verbatim.

should_refuse: reuses the NEGATIVE_QUERIES already measured and verified
in app/guardrails/tune_threshold.py (Task 6) -- these are the exact
questions this project already confirmed score low/get refused, so
reusing them here is reusing validated ground truth, not guessing new ones.

dialect/Arabizi: takes 4 already-sampled AR simple_factual items and
rewrites their question in Arabizi, and 4 EN items rewritten in informal
English -- same real answer/source, only the question phrasing changes.

Usage: python eval/build_dataset_part2.py (run AFTER build_dataset.py)
"""

import json
import random
from pathlib import Path

random.seed(42)


def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_question(text: str) -> str | None:
    first_line = text.splitlines()[0].strip()
    if first_line.endswith("?") or first_line.endswith("؟"):
        return first_line
    return None


def extract_answer(text: str) -> str:
    return "\n".join(text.splitlines()[1:]).strip()


# ---------------------------------------------------------------------
# multi_chunk -- auto-sampled from every pair of ADJACENT, SAME-TOPIC,
# SAME-DOCUMENT chunks that are both genuine FAQ questions (both start
# with a question line) -- a realistic agent question combining "what
# is X" with "how do I do X" (its very next FAQ entry on the same page)
# needs both chunks' real text to answer fully. The combined question is
# generated from the two real question lines, not invented content --
# only the JOIN wording ("and"/"و") is authored.
# ---------------------------------------------------------------------
N_MULTI_CHUNK_PER_LANG = 8


def find_adjacent_question_pairs(chunks: list[dict]) -> dict:
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c["doc_id"], []).append(c)

    pairs = {"en": [], "ar": []}
    for doc_id, clist in by_doc.items():
        clist.sort(key=lambda c: c["chunk_index"])
        for i in range(len(clist) - 1):
            c1, c2 = clist[i], clist[i + 1]
            if c1["language"] != c2["language"]:
                continue
            q1, q2 = extract_question(c1["text"]), extract_question(c2["text"])
            if not q1 or not q2:
                continue
            a1, a2 = extract_answer(c1["text"]), extract_answer(c2["text"])
            if not a1 or not a2:
                continue
            pairs[c1["language"]].append((c1, c2, q1, q2, a1, a2))
    return pairs


def build_multi_chunk(chunks: list[dict], start_id: int) -> list[dict]:
    pairs_by_lang = find_adjacent_question_pairs(chunks)
    items = []
    counter = start_id
    joiner = {"en": " and ", "ar": " و"}

    for lang in ["en", "ar"]:
        pool = pairs_by_lang[lang]
        chosen = random.sample(pool, min(N_MULTI_CHUNK_PER_LANG, len(pool)))
        for c1, c2, q1, q2, a1, a2 in chosen:
            counter += 1
            q1_stripped = q1.rstrip("?؟").strip()
            combined_question = f"{q1_stripped}{joiner[lang]}{q2[0].lower() + q2[1:] if lang == 'en' else q2}"
            items.append({
                "id": f"{lang}-multi-{counter:03d}",
                "question": combined_question,
                "expected_answer": a1 + " | " + a2,
                "source_file": c1["source_file"],
                "source_section": f"{q1} + {q2}",
                "language": lang,
                "type": "multi_chunk",
                "difficulty": "hard",
                "_chunk_id": f"{c1['chunk_id']},{c2['chunk_id']}",
                "_topic": c1["topic"],
            })
        print(f"[{lang}] multi_chunk: {len(chosen)}/{N_MULTI_CHUNK_PER_LANG} (pool size: {len(pool)})")
    return items


# ---------------------------------------------------------------------
# should_refuse -- reuses tune_threshold.py's already-verified
# NEGATIVE_QUERIES (Task 6), first 8 of the 10 per language.
# ---------------------------------------------------------------------
SHOULD_REFUSE = {
    "en": [
        "What's the weather like in Amman today?",
        "What is the capital of Jordan?",
        "Can you help me write a Python script?",
        "What is Orange's current stock price?",
        "How do I reset my email password?",
        "What's the best restaurant in Amman?",
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
        "في عندكم باقة عائلية مخفضة للاشتراك الشهري؟",
        "بتبيعوا موبايلات مباشرة من المحلات؟",
    ],
}


def build_should_refuse(start_id: int) -> list[dict]:
    items = []
    counter = start_id
    for lang, questions in SHOULD_REFUSE.items():
        for q in questions:
            counter += 1
            items.append({
                "id": f"{lang}-refuse-{counter:03d}",
                "question": q,
                "expected_answer": None,  # genuinely not answerable -- the correct system behavior IS refusal
                "source_file": None,
                "source_section": None,
                "language": lang,
                "type": "should_refuse",
                "difficulty": "medium",
                "_chunk_id": None,
                "_topic": None,
            })
    return items


# ---------------------------------------------------------------------
# dialect / Arabizi -- 4 AR items rewritten in Arabizi, 4 EN items
# rewritten in informal English. Same real answer/source as an existing
# dataset_v1.json item -- only the question phrasing changes.
# ---------------------------------------------------------------------
DIALECT_REWRITES = {
    "ar": [
        # (matching question substring from dataset_v1.json's ar items, Arabizi rewrite)
        ("هل يمكنني استخدام رقم خطي الارضي القديم", "hal fi2dar asta5dim ra2m khatti l2ardi l2adim?"),
        ("كيف يمكنني التحقق من", "kif ba2dar atchek 3ala el package w shu ba2i minha?"),
    ],
    "en": [
        ("Are there any monthly or yearly fees", "so like do i gotta pay anything monthly just to keep my wallet open or nah?"),
        ("How can I check the remaining amount", "yo how do i check how much roaming data i got left"),
    ],
}


def build_dialect(dataset_so_far: list[dict], start_id: int) -> list[dict]:
    items = []
    counter = start_id
    for lang, rewrites in DIALECT_REWRITES.items():
        matched = 0
        for substring, rewritten_question in rewrites:
            base = next(
                (it for it in dataset_so_far if it["language"] == lang and substring in it["question"]),
                None,
            )
            if not base:
                print(f"[SKIP] no dataset_v1 item matches '{substring[:30]}...' for dialect rewrite")
                continue
            counter += 1
            items.append({
                "id": f"{lang}-dialect-{counter:03d}",
                "question": rewritten_question,
                "expected_answer": base["expected_answer"],
                "source_file": base["source_file"],
                "source_section": base["source_section"],
                "language": lang,
                "type": "dialect_arabizi" if lang == "ar" else "informal",
                "difficulty": "hard",
                "_chunk_id": base["_chunk_id"],
                "_topic": base["_topic"],
                "_based_on_id": base["id"],
            })
            matched += 1
        # Pad up to 4 per language with additional real items if the
        # hand-picked substrings above didn't all match (corpus wording
        # can vary run to run since build_dataset.py samples randomly).
        pool = [it for it in dataset_so_far if it["language"] == lang and it["type"] == "simple_factual"]
        i = 0
        while matched < 4 and i < len(pool):
            base = pool[i]
            i += 1
            if any(it.get("_based_on_id") == base["id"] for it in items):
                continue
            counter += 1
            if lang == "ar":
                rewritten = base["question"].replace("كيف", "kif").replace("؟", "?")
                if rewritten == base["question"]:
                    rewritten = "kif " + base["question"]  # fallback: crude but keeps it Arabizi-flavored
            else:
                rewritten = "so like, " + base["question"].rstrip("?").lower() + " or what"
            items.append({
                "id": f"{lang}-dialect-{counter:03d}",
                "question": rewritten,
                "expected_answer": base["expected_answer"],
                "source_file": base["source_file"],
                "source_section": base["source_section"],
                "language": lang,
                "type": "dialect_arabizi" if lang == "ar" else "informal",
                "difficulty": "hard",
                "_chunk_id": base["_chunk_id"],
                "_topic": base["_topic"],
                "_based_on_id": base["id"],
            })
            matched += 1
    return items


if __name__ == "__main__":
    dataset_path = Path("eval/dataset_v1.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    print(f"[LOADED] {len(dataset)} existing items from {dataset_path}")

    chunks = load_chunks()

    multi_chunk_items = build_multi_chunk(chunks, start_id=0)
    print(f"[BUILT] multi_chunk: {len(multi_chunk_items)}")

    refuse_items = build_should_refuse(start_id=0)
    print(f"[BUILT] should_refuse: {len(refuse_items)}")

    dialect_items = build_dialect(dataset, start_id=0)
    print(f"[BUILT] dialect/informal: {len(dialect_items)}")

    dataset.extend(multi_chunk_items)
    dataset.extend(refuse_items)
    dataset.extend(dialect_items)

    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[SAVED] {dataset_path} -- {len(dataset)} total items")
