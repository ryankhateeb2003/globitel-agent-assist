"""
Task 6 -- Guardrails for the /ask endpoint: the refusal/clarification
behaviour for the 6 "hard cases" the task brief defines (no relevant
chunk, out-of-domain question, conflicting sources, ambiguous question,
question needing customer account data, and dialect/Arabizi input).

Deliberately reuses the ONE Groq client + model already configured in
app/api/main.py for everything here (intent classification and Arabizi
transliteration) instead of adding a second model -- every function that
needs the LLM takes `client` and `model` as arguments rather than
constructing its own, so app/api/main.py stays the single place that
knows about Groq credentials/config.

"Sources conflict" is not handled here as a branch -- it is handled by
an instruction added to the prompt templates (prompts/rag_answer_*.txt),
because it is about how the final answer is *worded*, not a pre-check
that should block generation.
"""

import json
import re

# ---------------------------------------------------------------------
# Relevance threshold -- "no relevant chunk found"
# ---------------------------------------------------------------------

# Tuned per language by tune_threshold.py (see threshold-tuning.md for
# the measured positive/negative score distributions these numbers come
# from -- these are not guesses). Compared against the top retrieved
# result's confidence score: `rerank_score` for hybrid mode (the /ask
# default, and the score the reranker itself produces, roughly 0-1), or
# `score` (raw vector/BM25 similarity) as a fallback for the other two
# modes, since they never carry a rerank_score.
RELEVANCE_THRESHOLDS = {
    "en": 0.30,
    "ar": 0.30,
}

# A separate, lower threshold for queries that went through the Arabizi
# transliteration override (main.py's `retrieval_question =
# transliterate_arabizi(...)` path). Manual testing found a genuinely
# correct top-1 match scoring as low as 0.095 for an Arabizi-origin query
# -- the LLM transliteration step adds noise the reranker wasn't trained
# around, so the *same* confidence number means less for these queries
# than for a native-script Arabic one. Using the normal "ar" threshold
# here would systematically refuse answerable Arabizi questions, which
# directly contradicts Task 6's requirement that dialect/Arabizi input
# must still be answered. Value is provisional (see threshold-tuning.md's
# Arabizi section for the measured positive/negative scores behind it)
# pending a larger sample.
ARABIZI_RELEVANCE_THRESHOLD = 0.05


def top_score(results: list[dict]) -> float | None:
    """Best-available confidence score for the top retrieved result,
    mode-agnostic."""
    if not results:
        return None
    top = results[0]
    return top.get("rerank_score", top.get("score"))


def passes_relevance_threshold(results: list[dict], language: str, is_arabizi_query: bool = False) -> bool:
    score = top_score(results)
    if score is None:
        return False
    threshold = (
        ARABIZI_RELEVANCE_THRESHOLD if is_arabizi_query
        else RELEVANCE_THRESHOLDS.get(language, RELEVANCE_THRESHOLDS["en"])
    )
    return score >= threshold


# ---------------------------------------------------------------------
# Arabizi detection + transliteration
# ---------------------------------------------------------------------

_ARABIC_CHAR_PATTERN = re.compile(r"[؀-ۿ]")
_LATIN_CHAR_PATTERN = re.compile(r"[A-Za-z]")

# Digits commonly used as letter substitutes in Arabizi texting (2 for
# ء/ع, 3 for ع, 5 for خ, 6 for ط, 7 for ح, 8 for غ/ق, 9 for ص) -- their
# presence is a strong Arabizi signal that app/rag/language_detect.py's
# Arabic-character-ratio check cannot see at all, since Arabizi has zero
# Arabic-script characters by definition (that gap is exactly what
# language_detect.py's own docstring flags as untested).
#
# Requires the digit to sit inside the same run as a Latin letter (e.g.
# "ba3mal", "3am") rather than matching any bare digit anywhere in the
# text -- otherwise a short code like "*140#" (digit "0" present, no
# letters attached) would false-positive as Arabizi.
_ARABIZI_DIGIT_PATTERN = re.compile(
    r"[a-zA-Z]+[23567890][a-zA-Z]*|[a-zA-Z]*[23567890][a-zA-Z]+"
)

# A short list of very common Levantine/Arabizi function words -- not
# exhaustive, just enough to catch the "no digits used" case (e.g. "shu
# ba3mal" has an 3, but "kif fi ashtare" doesn't use any digit at all).
_ARABIZI_WORD_PATTERN = re.compile(
    r"\b(kif|shu|shou|leish|lesh|wein|fi|mnih|eno|ba3mal|3am|3ala|ktir|hala2|halla2|"
    r"badde|biddi|mfeed|2diesh|adesh|kam|tab|yalla|sar|sarly)\b",
    re.IGNORECASE,
)


def is_arabizi(text: str) -> bool:
    """
    Heuristic: no real Arabic script present, at least a few Latin
    letters, and either an Arabizi-style digit-as-letter or a recognised
    Levantine/Arabizi function word.
    """
    if not text or not text.strip():
        return False
    if _ARABIC_CHAR_PATTERN.search(text):
        return False  # already has real Arabic script -- not Arabizi

    if len(_LATIN_CHAR_PATTERN.findall(text)) < 3:
        return False

    return bool(_ARABIZI_DIGIT_PATTERN.search(text) or _ARABIZI_WORD_PATTERN.search(text))


def transliterate_arabizi(client, model: str, text: str) -> str:
    """
    One Groq call: Arabizi (Arabic written in Latin letters/digits) ->
    Modern Standard Arabic script. Used only to build a better retrieval
    query -- the customer's original wording is still what gets shown to
    the answering model and recorded in metadata.
    """
    prompt = (
        "Transliterate the following Arabizi text (Levantine Arabic "
        "written in Latin letters and digits) into Modern Standard "
        "Arabic script. Output ONLY the Arabic transliteration, nothing "
        "else -- no explanation, no quotes.\n\n"
        f"Text: {text}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="none",
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------
# Intent classification -- domain / account-data / ambiguity, one call
# ---------------------------------------------------------------------

_CLASSIFY_PROMPT_TEMPLATE = """You are a guardrail classifier for an Orange Jordan telecom contact-center assistant. The assistant only answers from documentation covering: mobile phone lines and plans, fiber/ADSL internet, the Orange Money mobile wallet, international roaming, bill payment, and service short codes.

Given the customer's question, the topics found by a document search, and a preview of the best-matching document content actually found, decide THREE things:

1. in_domain: is this question plausibly about Orange Jordan's telecom or wallet services -- even if the documentation might not cover this exact detail? Answer false ONLY for questions clearly unrelated to telecom/wallet services (general knowledge, other companies, casual chat, coding help, etc).
2. needs_account_data: does answering truly require looking up THIS SPECIFIC customer's live personal data (their current balance right now, their actual bill amount, why THEY specifically were charged, their personal transaction history) that no general document could ever contain?
   - Do NOT flag this just because the question is phrased with "my"/"I" (e.g. "how do I check my remaining limit?", "how do I top up my wallet?") -- a personal pronoun does not by itself mean personal data is needed.
   - Look at the retrieved content preview below: if it already contains a general, reusable answer (instructions, a method, a code to dial, a policy that is the same for every customer), the question does NOT need account data, even if it was phrased personally -- decide false and let the generic answer be used.
   - Only decide true when no generic instruction could possibly answer it -- the question is fundamentally about a live, individual number or event (a specific balance, a specific charge, a specific transaction), not "how" or "where" to find/do something.
   - Worked examples: "How do I check my remaining roaming limit?" with a retrieved chunk that says "check via Max it app or dial *979#" -> false (that's a reusable instruction). "Why was I charged 5 JOD last month?" -> true (no document can contain the answer to one customer's specific past charge).
3. is_ambiguous: as phrased, could this question reasonably refer to more than one distinct service/topic, such that you could not confidently answer without asking which one? Use the retrieved topics as a hint of what's nearby in the documentation.

Respond with ONLY a JSON object and nothing else -- no markdown fences, no explanation:
{{"in_domain": true or false, "needs_account_data": true or false, "is_ambiguous": true or false, "clarifying_question": "<one short clarifying question in {language_name}, or null if not ambiguous>"}}

Question: {question}
Retrieved document topics: {topics}
Best-matching content preview:
{content_preview}
"""

_LANGUAGE_NAMES = {"ar": "Arabic", "en": "English"}

# How many top results' text to show the classifier, and how much of
# each -- enough for the model to judge "is this a generic, reusable
# answer" without ballooning the prompt (this call is on the latency
# path of every request).
_PREVIEW_CHUNK_COUNT = 2
_PREVIEW_CHARS_PER_CHUNK = 300


def _build_content_preview(results: list[dict]) -> str:
    if not results:
        return "(no results found)"
    previews = []
    for r in results[:_PREVIEW_CHUNK_COUNT]:
        text = r.get("text", "")[:_PREVIEW_CHARS_PER_CHUNK]
        previews.append(f"- {text}")
    return "\n".join(previews)


def classify_intent(client, model: str, question: str, language: str, results: list[dict]) -> dict:
    """
    Single Groq call bundling the domain / account-data / ambiguity
    checks together -- deliberately one call, not three, since this is a
    live-call product where every extra network round trip is latency a
    contact-center agent is waiting through (same reasoning Task 4 used
    for streaming).

    Takes the full retrieved `results` (not just topic names) so the
    needs_account_data check can weigh actual document content, not just
    the question's phrasing -- see the prompt's worked examples for why.
    """
    topics = sorted({r["topic"] for r in results if r.get("topic")})
    prompt = _CLASSIFY_PROMPT_TEMPLATE.format(
        question=question,
        topics=", ".join(topics) if topics else "(none found)",
        content_preview=_build_content_preview(results),
        language_name=_LANGUAGE_NAMES.get(language, "English"),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="none",
    )
    raw = response.choices[0].message.content or ""

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Model occasionally wraps the JSON in a code fence or adds a
        # stray sentence despite the instruction -- pull out the first
        # {...} block rather than failing the whole request over it.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}

    return {
        "in_domain": parsed.get("in_domain", True),
        "needs_account_data": parsed.get("needs_account_data", False),
        "is_ambiguous": parsed.get("is_ambiguous", False),
        "clarifying_question": parsed.get("clarifying_question"),
    }


# ---------------------------------------------------------------------
# Refusal message text, per language (static, not LLM-generated, so
# wording is controlled and testable rather than left to model output)
# ---------------------------------------------------------------------

REFUSAL_MESSAGES = {
    "no_info": {
        "en": "I don't have this information in the documentation. Please check with a supervisor or the relevant system.",
        "ar": "لا تتوفر لدي هذه المعلومة في التوثيق. يرجى التحقق مع المشرف أو النظام المعني.",
    },
    "out_of_domain": {
        "en": "I can only help with questions about Orange Jordan's mobile lines, internet, wallet, roaming, billing, and short-code services. This question is outside that scope.",
        "ar": "أستطيع المساعدة فقط بالأسئلة المتعلقة بخدمات اورنج الاردن: الخطوط، الانترنت، المحفظة، التجوال، الفواتير، والأكواد القصيرة. هذا السؤال خارج هذا النطاق.",
    },
    "needs_account_data": {
        "en": "Answering this requires checking the customer's specific account. Please look it up in the relevant system rather than relying on this answer.",
        "ar": "الإجابة على هذا تتطلب التحقق من حساب الزبون تحديدًا. يرجى مراجعة النظام المعني بدلًا من الاعتماد على هذا الجواب.",
    },
}


def refusal_text(reason: str, language: str) -> str:
    return REFUSAL_MESSAGES[reason].get(language, REFUSAL_MESSAGES[reason]["en"])


# ---------------------------------------------------------------------
# Top-level decision -- combines everything above into one action
# ---------------------------------------------------------------------

def decide_action(
    client, model: str, question: str, language: str, results: list[dict],
    is_arabizi_query: bool = False,
) -> dict:
    """
    Runs the classifier and the threshold check and returns exactly one
    action for app/api/main.py to act on:

      {"action": "out_of_domain"}
      {"action": "needs_account_data"}
      {"action": "ambiguous", "clarifying_question": "..."}
      {"action": "no_info"}
      {"action": "answer_normally"}

    Priority order and why: domain and account-data are decided from the
    question's content alone, independent of how retrieval went, so they
    are checked first. Ambiguity is checked next since it uses retrieval
    (the spread of topics found) as a hint. The relevance threshold is
    checked last, as the final fallback -- a question can be in-domain,
    unambiguous, and not need account data, and still find nothing in
    the docs.

    `is_arabizi_query` picks ARABIZI_RELEVANCE_THRESHOLD instead of the
    normal per-language one for that last check -- see its definition for
    why the same confidence number needs a lower bar for these queries.
    """
    verdict = classify_intent(client, model, question, language, results)

    if not verdict["in_domain"]:
        return {"action": "out_of_domain"}

    if verdict["needs_account_data"]:
        return {"action": "needs_account_data"}

    if verdict["is_ambiguous"] and verdict["clarifying_question"]:
        return {"action": "ambiguous", "clarifying_question": verdict["clarifying_question"]}

    if not passes_relevance_threshold(results, language, is_arabizi_query):
        return {"action": "no_info"}

    return {"action": "answer_normally"}
