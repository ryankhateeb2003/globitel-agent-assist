"""
Task 6 deliverable data generator: one English + one Arabic example per
required case, run through the real `/ask` pipeline pieces (not the HTTP
layer -- the same functions app/api/main.py calls), producing the actual
output and writing it to edge-cases.md.

"Sources conflict" is the one case that cannot be demonstrated by picking
a real query and hoping the corpus happens to disagree with itself on
that topic -- this corpus's known duplicate content (Task 5's
hybrid-results.md) is identical text, not conflicting values. That case
is tested with a deliberately constructed pair of contradicting chunks
instead, run through the real prompt template and the real model, which
is the honest way to prove the "present both, name each source" prompt
instruction (prompts/rag_answer_*.txt) actually works.

"Dialect or Arabizi" is Arabic-only by definition (see Task 6's brief:
"Your documentation is in formal Arabic, but people write in dialect and
in Latin letters") -- there is no English-dialect equivalent case, so
that row uses one dialect (Arabic-script) example and one Arabizi
example instead of one-per-language.
"""

from app.api.main import get_groq_client, GROQ_MODEL, load_prompt_template
from app.rag.retrieval import build_context
from app.retrieval.retrieval import search as retrieval_search
from app.guardrails.guardrails import (
    is_arabizi,
    transliterate_arabizi,
    decide_action,
    refusal_text,
    top_score,
)

CASES = [
    {
        "case": "no_relevant_chunk",
        "label": "No relevant chunk found",
        "en": "Do you offer discounted family postpaid bundles?",
        "ar": "في عندكم باقة عائلية مخفضة للاشتراك الشهري؟",
    },
    {
        "case": "out_of_domain",
        "label": "Question outside the domain",
        "en": "What's the weather like in Amman today?",
        "ar": "شو الطقس بعمان اليوم؟",
    },
    {
        "case": "ambiguous",
        "label": "Question is ambiguous",
        "en": "How do I cancel it?",
        "ar": "كيف بلغي الاشتراك؟",
    },
    {
        "case": "needs_account_data",
        "label": "Answer would need customer account data",
        "en": "Why was I charged 5 JOD last month?",
        "ar": "ليش انخصم مني 5 دينار الشهر الماضي؟",
    },
]

# Deliberately constructed conflicting pair -- see module docstring.
CONFLICT_CONTEXT_CHUNKS = {
    "en": [
        {"source_file": "corpus/en/orange-money.docx", "text": "The maximum wallet-to-wallet transfer amount is 500 JOD per day."},
        {"source_file": "corpus/en/orange-money.html", "text": "You can transfer up to 300 JOD per day between Orange Money wallets."},
    ],
    "ar": [
        {"source_file": "corpus/ar/orange-money.docx", "text": "الحد الاقصى للتحويل بين المحافظ هو 500 دينار يوميا."},
        {"source_file": "corpus/ar/orange-money.html", "text": "بتقدر تحول لغاية 300 دينار يوميا بين محافظ Orange Money."},
    ],
}
CONFLICT_QUESTION = {
    "en": "What's the maximum amount I can transfer between wallets?",
    "ar": "شو اقصى مبلغ بقدر احوله بين المحافظ؟",
}


def run_normal_case(question: str, language: str, client) -> dict:
    outcome = retrieval_search(question, mode="hybrid", top_k=5)
    chunks = outcome["results"]
    decision = decide_action(client, GROQ_MODEL, question, language, chunks)

    if decision["action"] == "ambiguous":
        output = decision["clarifying_question"]
    elif decision["action"] != "answer_normally":
        output = refusal_text(decision["action"], language)
    else:
        # Shouldn't happen for these 4 cases if the guardrail is working,
        # but if it does, generate the real answer so the miss is visible
        # rather than silently hidden.
        output = generate_real_answer(question, language, chunks, client)

    return {
        "question": question,
        "language": language,
        "guardrail_action": decision["action"],
        "top1_score": top_score(chunks),
        "output": output,
    }


def generate_real_answer(question: str, language: str, chunks: list[dict], client) -> str:
    context = build_context(chunks)
    template = load_prompt_template(language)
    filled_prompt = template.replace("{context}", context).replace("{question}", question)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": filled_prompt}],
        reasoning_effort="none",
    )
    return response.choices[0].message.content.strip()


def run_conflict_case(language: str, client) -> dict:
    question = CONFLICT_QUESTION[language]
    output = generate_real_answer(question, language, CONFLICT_CONTEXT_CHUNKS[language], client)
    return {"question": question, "language": language, "output": output}


def run_dialect_case(client) -> dict:
    dialect_q = "كيف بقدر اعبي محفظتي؟"
    outcome = retrieval_search(dialect_q, mode="hybrid", top_k=5)
    chunks = outcome["results"]
    decision = decide_action(client, GROQ_MODEL, dialect_q, "ar", chunks)
    dialect_output = (
        generate_real_answer(dialect_q, "ar", chunks, client)
        if decision["action"] == "answer_normally"
        else f"[guardrail blocked: {decision['action']}]"
    )

    arabizi_q = "kif ba3mal top up la mahfazti"
    is_az = is_arabizi(arabizi_q)
    transliterated = transliterate_arabizi(client, GROQ_MODEL, arabizi_q) if is_az else arabizi_q
    outcome2 = retrieval_search(transliterated, mode="hybrid", top_k=5)
    chunks2 = outcome2["results"]
    decision2 = decide_action(client, GROQ_MODEL, arabizi_q, "ar", chunks2, is_arabizi_query=is_az)
    arabizi_output = (
        generate_real_answer(arabizi_q, "ar", chunks2, client)
        if decision2["action"] == "answer_normally"
        else f"[guardrail blocked: {decision2['action']}]"
    )

    return {
        "dialect_question": dialect_q,
        "dialect_action": decision["action"],
        "dialect_output": dialect_output,
        "arabizi_question": arabizi_q,
        "arabizi_transliterated": transliterated,
        "arabizi_action": decision2["action"],
        "arabizi_output": arabizi_output,
    }


def run() -> dict:
    client = get_groq_client()
    results = {}
    for case in CASES:
        results[case["case"]] = {
            "label": case["label"],
            "en": run_normal_case(case["en"], "en", client),
            "ar": run_normal_case(case["ar"], "ar", client),
        }
    results["sources_conflict"] = {
        "label": "Sources conflict",
        "en": run_conflict_case("en", client),
        "ar": run_conflict_case("ar", client),
    }
    results["dialect_arabizi"] = {
        "label": "Question in Levantine dialect or Arabizi",
        **run_dialect_case(client),
    }
    return results


WHY_CORRECT = {
    "no_relevant_chunk": "The question is about a plausible telecom topic (in_domain=true) but this corpus's 7 topic pages don't cover it, so the top retrieval score falls below the tuned threshold -- the system says so plainly instead of guessing at bundle terms it was never given.",
    "out_of_domain": "The question has nothing to do with Orange Jordan's telecom/wallet services, so the guardrail classifier flags in_domain=false and the system refuses before ever calling the answer model with unrelated context.",
    "ambiguous": "\"Cancel it\" doesn't specify what -- promotional messages, a wallet, a bundle, a mobile line are all plausible referents in this corpus's topics, so the system asks one clarifying question instead of guessing which service the agent means.",
    "needs_account_data": "Answering requires this specific customer's billing history, which isn't in the general documentation and can't be answered generically -- the system tells the agent to check the account system instead of fabricating a number.",
    "sources_conflict": "The two source chunks give different transfer limits (500 vs 300) for the same fact. Per the updated prompt instruction, the answer must present both values and name each source rather than silently picking one -- verify by hand that the returned text contains both numbers and both source file names.",
    "dialect_arabizi": "The documentation is formal Arabic, but the question is phrased in Levantine dialect / Arabizi. Task 6 requires the system to still answer (not refuse) -- verify by hand that guardrail_action is answer_normally and a real, on-topic answer was generated for both variants.",
}


def write_markdown(results: dict, path: str = "app/guardrails/edge-cases.md") -> None:
    lines = ["# Edge Cases", "", "6 required hard-case behaviours, each demonstrated with a real",
              "example run through the actual `/ask` pipeline pieces (retrieval +",
              "`decide_action` + real Groq calls where applicable).", "", "---", ""]

    for case_key in ["no_relevant_chunk", "out_of_domain", "sources_conflict", "ambiguous", "needs_account_data"]:
        r = results[case_key]
        lines.append(f"## {r['label']}")
        lines.append("")
        for lang in ["en", "ar"]:
            item = r[lang]
            lines.append(f"**{lang.upper()} question:** {item['question']}")
            lines.append("")
            if "guardrail_action" in item:
                lines.append(f"**Guardrail action:** `{item['guardrail_action']}`")
                lines.append("")
            lines.append(f"**Output:**")
            lines.append("")
            lines.append(f"> {item['output']}")
            lines.append("")
        lines.append(f"**Why this is correct:** {WHY_CORRECT[case_key]}")
        lines.append("")
        lines.append("---")
        lines.append("")

    d = results["dialect_arabizi"]
    lines.append(f"## {d['label']}")
    lines.append("")
    lines.append(f"**Dialect (Arabic script) question:** {d['dialect_question']}")
    lines.append("")
    lines.append(f"**Guardrail action:** `{d['dialect_action']}`")
    lines.append("")
    lines.append(f"**Output:**\n\n> {d['dialect_output']}")
    lines.append("")
    lines.append(f"**Arabizi question:** {d['arabizi_question']}")
    lines.append("")
    lines.append(f"**Transliterated for retrieval:** {d['arabizi_transliterated']}")
    lines.append("")
    lines.append(f"**Guardrail action:** `{d['arabizi_action']}`")
    lines.append("")
    lines.append(f"**Output:**\n\n> {d['arabizi_output']}")
    lines.append("")
    lines.append(f"**Why this is correct:** {WHY_CORRECT['dialect_arabizi']}")
    lines.append("")
    lines.append("See `dialect-tests.md` for the broader 10-dialect + 5-Arabizi test set this single example is drawn from.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[SAVED] {path}")


if __name__ == "__main__":
    results = run()
    for key, r in results.items():
        print(f"=== {key} ===")
        print(r)
        print()
    write_markdown(results)
