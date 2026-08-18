"""
Task 6 deliverable data generator: runs 10 Levantine-dialect Arabic
questions (written in Arabic script, informal phrasing rather than MSA)
and 5 Arabizi questions (Arabic typed in Latin letters/digits) through
the real /ask pipeline pieces -- language detection + Arabizi override,
retrieval, and decide_action -- and reports what happened into
dialect-tests.md, including where the pipeline still gets it wrong.

This does not call the FastAPI endpoint over HTTP; it drives the same
functions app/api/main.py calls, which avoids needing a running server
while still exercising the exact production code path.
"""

from app.api.main import get_groq_client, GROQ_MODEL
from app.rag.language_detect import detect_language
from app.retrieval.retrieval import search as retrieval_search
from app.guardrails.guardrails import is_arabizi, transliterate_arabizi, decide_action, top_score

DIALECT_QUERIES = [
    "كيف بقدر اعبي محفظتي؟",
    "شو بصير اذا نسيت ادفع فاتورتي؟",
    "بدي افصل خدمة الرسايل الدعائية شو اعمل؟",
    "قديش بتكلفني المكالمة عالخط الثاني؟",
    "في طريقة احدد حد التجوال تبعي؟",
    "كيف بعرف قديش صرف من باقتي؟",
    "ممكن احول مصاري من محفظتي لصاحبي؟",
    "وين بقدر ادفع فاتورة الانترنت من البيت؟",
    "شو الكود يلي بدي دق عليه احدد رصيدي؟",
    "في غرامة اذا تأخرت بدفع الفاتورة؟",
]

ARABIZI_QUERIES = [
    "kif ba3mal top up la mahfazti",
    "shu el code la ashoof rasidi",
    "fi 7ad la data el tajwal?",
    "kiff ba2dar ad-fa3 fatoorti",
    "leish in-khasam meni floos zyada?",
]


def run_one(question: str, client, is_arabizi_query: bool) -> dict:
    naive_detected = detect_language(question)

    retrieval_question = question
    override_applied = False
    transliterated = None
    if is_arabizi_query and is_arabizi(question):
        override_applied = True
        transliterated = transliterate_arabizi(client, GROQ_MODEL, question)
        retrieval_question = transliterated

    final_language = "ar" if override_applied else naive_detected

    outcome = retrieval_search(retrieval_question, mode="hybrid", top_k=5)
    chunks = outcome["results"]
    decision = decide_action(
        client, GROQ_MODEL, question, final_language, chunks,
        is_arabizi_query=override_applied,
    )

    return {
        "question": question,
        "naive_detected_language": naive_detected,
        "is_arabizi_detected": is_arabizi(question),
        "arabizi_override_applied": override_applied,
        "transliterated_query": transliterated,
        "final_language": final_language,
        "top1_score": top_score(chunks),
        "top1_topic": chunks[0]["topic"] if chunks else None,
        "top1_preview": chunks[0]["text"][:100].replace("\n", " ") if chunks else None,
        "guardrail_action": decision["action"],
        "still_answers": decision["action"] == "answer_normally",
    }


def run() -> dict:
    client = get_groq_client()

    dialect_results = [run_one(q, client, is_arabizi_query=False) for q in DIALECT_QUERIES]
    arabizi_results = [run_one(q, client, is_arabizi_query=True) for q in ARABIZI_QUERIES]

    return {"dialect": dialect_results, "arabizi": arabizi_results}


def write_markdown(outcome: dict, path: str = "app/guardrails/dialect-tests.md") -> None:
    dialect_ok = sum(1 for r in outcome["dialect"] if r["still_answers"])
    arabizi_ok = sum(1 for r in outcome["arabizi"] if r["still_answers"])
    arabizi_detected = sum(1 for r in outcome["arabizi"] if r["is_arabizi_detected"])

    lines = [
        "# Dialect and Arabizi Tests",
        "",
        "## Method",
        "",
        "10 Levantine-dialect Arabic questions (Arabic script, informal "
        "phrasing rather than MSA) and 5 Arabizi questions (Arabic typed "
        "in Latin letters/digits) run through the real `/ask` pipeline "
        "pieces: language detection, `is_arabizi()` detection and the "
        "transliteration override, retrieval, and `decide_action()`. "
        "Task 6 requires the system to still answer these -- this is not "
        "a refusal case.",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- Dialect (Arabic script): **{dialect_ok}/{len(outcome['dialect'])}** "
        "still answered normally (did not incorrectly refuse)",
        f"- Arabizi: **{arabizi_ok}/{len(outcome['arabizi'])}** still answered "
        f"normally; **{arabizi_detected}/{len(outcome['arabizi'])}** were "
        "correctly detected as Arabizi by `is_arabizi()`",
        "",
        "---",
        "",
        "## Dialect (Arabic script) results",
        "",
        "| Question | Top-1 topic | Top-1 score | Guardrail action | Still answers? |",
        "|---|---|---:|---|---|",
    ]
    for r in outcome["dialect"]:
        score = f"{r['top1_score']:.4f}" if r["top1_score"] is not None else "n/a"
        lines.append(
            f"| {r['question']} | {r['top1_topic'] or '—'} | {score} | "
            f"{r['guardrail_action']} | {'✅' if r['still_answers'] else '❌'} |"
        )

    lines += ["", "---", "", "## Arabizi results", "",
              "| Question | Transliterated | Top-1 topic | Top-1 score | Guardrail action | Still answers? |",
              "|---|---|---|---:|---|---|"]
    for r in outcome["arabizi"]:
        score = f"{r['top1_score']:.4f}" if r["top1_score"] is not None else "n/a"
        lines.append(
            f"| {r['question']} | {r['transliterated_query'] or '—'} | "
            f"{r['top1_topic'] or '—'} | {score} | {r['guardrail_action']} | "
            f"{'✅' if r['still_answers'] else '❌'} |"
        )

    lines += ["", "---", "", "## Analysis of what broke", "",
              "(Fill in after a real run: note any row where `still_answers` "
              "is ❌ -- was it a language-detection miss, a retrieval miss "
              "against dialect/Arabizi phrasing, or the guardrail classifier "
              "wrongly flagging the question as out-of-domain/ambiguous? "
              "Compare the dialect accuracy rate against Task 5's "
              "hybrid-results.md formal-Arabic accuracy to state the "
              "measured cost of dialect input, per Task 6's Done-when line.)"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[SAVED] {path}")


if __name__ == "__main__":
    outcome = run()
    for group in ["dialect", "arabizi"]:
        for r in outcome[group]:
            print(f"[{group}] answers={r['still_answers']} action={r['guardrail_action']} "
                  f"score={r['top1_score']} :: {r['question'][:50]}")
    write_markdown(outcome)
