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

# Matches actual Arabic LETTERS only -- deliberately narrower than the
# full Arabic Unicode block (U+0600-U+06FF), which also contains
# punctuation (، U+060C, ؛ U+061B, ؟ U+061F) and the Arabic-Indic digits
# (٠-٩ U+0660-0669). The original version of this pattern used the full
# block, so an Arabizi question typed with a Latin-letter body but an
# Arabic question mark at the end (e.g. "shu ye3ni QR payment؟") matched
# it on the "؟" alone and was wrongly treated as "already has real
# Arabic script" -- is_arabizi() returned False and the question lost
# its Arabizi handling (bilingual search, softened relevance threshold)
# even though it was Arabizi in every way that mattered. Restricting the
# match to the letter ranges below (main block U+0621-064A plus the
# less common presentation-form letters used in loanwords/names) fixes
# that without weakening the "is this actually Arabic-script text"
# check itself -- punctuation and digits were never a signal of real
# Arabic *script* being present anyway.
_ARABIC_CHAR_PATTERN = re.compile(
    r"[ء-غـ-يٮٯٱ-ۓەۮۯۺ-ۿ]"
)
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
        # Pinned low so the same Arabizi input transliterates the same
        # way every time -- previously unset (Groq's default is not 0),
        # so identical questions could retrieve different chunks across
        # runs purely because the transliteration text itself changed.
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def translate_arabizi_bilingual(client, model: str, text: str) -> dict:
    """
    One Groq call: Arabizi -> BOTH a Modern Standard Arabic transliteration
    AND an English translation. Separate function from
    transliterate_arabizi() (not a signature change to it) so existing
    callers (eval_dialect.py, eval_edge_cases.py, test_guardrails.py) are
    untouched.

    Why both languages: found via manual testing that some FAQ answers in
    this corpus exist in ONLY one language (e.g. "Does an Electronic
    Voucher expire?" has no Arabic counterpart at all). An Arabizi
    question about it, transliterated to Arabic only, searches an Arabic
    query against an English-only answer -- relying on cross-language
    embedding matching through a second layer of translation noise on
    top of the original Arabizi-to-Arabic step. Translating to English
    too and searching with both lets retrieval find the chunk directly
    in whichever language it actually exists in, the same way a customer
    who typed the question in clean English or clean Arabic already can.
    """
    prompt = (
        "The following text is Arabizi (Levantine Arabic written in Latin "
        "letters and digits). Produce TWO things: a Modern Standard "
        "Arabic transliteration, and an English translation of the same "
        "meaning. Respond with ONLY a JSON object, no markdown fences, no "
        "explanation:\n"
        '{"arabic": "<Arabic transliteration>", "english": "<English translation>"}\n\n'
        f"Text: {text}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="none",
        temperature=0,  # same input -> same translation every time
    )
    raw = response.choices[0].message.content or ""

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}

    # Fall back to the Arabizi original for whichever side didn't parse,
    # rather than crashing the request over a malformed classifier reply.
    return {
        "arabic": parsed.get("arabic") or text,
        "english": parsed.get("english") or text,
    }


def merge_chunk_lists(*chunk_lists: list[dict]) -> list[dict]:
    """
    Deduplicates retrieved chunks (by chunk_id) across multiple retrieval
    passes -- e.g. one run against an Arabic-transliterated query and one
    against an English-translated query for the same Arabizi question --
    keeping each chunk's best score across the passes it appeared in, and
    returns them sorted best-first. Used instead of just concatenating
    lists so a chunk found strongly by one language pass isn't buried
    under weaker duplicates of itself from the other pass.
    """
    best_by_id: dict[str, dict] = {}

    for chunks in chunk_lists:
        for chunk in chunks:
            cid = chunk.get("chunk_id")
            if cid is None:
                continue
            score = chunk.get("rerank_score", chunk.get("score", 0))
            existing = best_by_id.get(cid)
            existing_score = existing.get("rerank_score", existing.get("score", 0)) if existing else None
            if existing is None or score > existing_score:
                best_by_id[cid] = chunk

    return sorted(
        best_by_id.values(),
        key=lambda c: c.get("rerank_score", c.get("score", 0)),
        reverse=True,
    )


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
3. is_ambiguous: as phrased, could this question reasonably refer to more than one distinct service/topic, such that you could not confidently answer without asking which one?
   - First check the content preview below: if its TOP item already directly and specifically answers the question (e.g. it is the same question, near-verbatim, or gives a complete, on-topic answer) AND no other item is comparably strong, this is NOT ambiguous -- decide false and let that answer be used. A single strong match beats the mere presence of other topics.
   - Decide true in either of two situations: (a) the question itself is genuinely underspecified (a vague pronoun like "it"/"cancel it" with no clear referent, or a term that could equally mean two unrelated things), or (b) the preview shows several (more than two or three) genuinely distinct, comparably-relevant real answers -- e.g. multiple region/country/type variants of the same templated FAQ (different codes, different conditions) with no single one standing out as THE answer. Case (b) applies even though each individual item looks like a strong match -- the ambiguity is that there are too many equally strong matches, not that any one is weak.
   - If the customer already narrowed it down (e.g. added "via international roaming" or "in Orange Money", or named the specific region/country) to a previously vague or multi-option question, treat that as resolved -- do not ask the same either/or question again, and do not flag case (b) once only one variant remains relevant. Re-decide based on the new, more specific wording.
   - When you do decide true, clarifying_question MUST be built ONLY from the actual distinct questions/topics visible in the content preview below -- quote or closely paraphrase what is really there. Never invent plausible-sounding categories (a service, a feature, a scenario) that do not literally appear in the preview -- that is fabrication, not clarification, and it is worse than asking nothing. For case (b) specifically: list EVERY genuinely distinct real option visible in the preview (not just two, and not a silent partial subset) so the customer can pick the exact one that applies to them -- do not merge them into one long answer, and do not drop any that are shown to you.
   - Worked example (case a): question "How do I cancel it?" with a preview containing "Can I cancel an International Money transfer?" (topic: orange-money) and a roaming chunk about disabling the bill-control feature (topic: international-roaming) -> true, clarifying_question asks specifically about "cancelling an international money transfer" vs "the roaming bill control feature" -- the two real things actually found, not generic invented categories like "a subscription" or "your account".
   - Worked example (case b): question "How can I subscribe to Passenger Bundles?" (no region named) with a preview containing "How can I subscribe to Asia Passenger Bundles? Dial *967#", "...Africa Passenger Bundles? Dial *964#", "...Palestine Passenger Bundles? Dial *970#", and more region variants, all comparably relevant -> true, clarifying_question asks which region/destination (naming every region actually present in the preview), not a merged answer reciting every code in one breath.

Respond with ONLY a JSON object and nothing else -- no markdown fences, no explanation:
{{"in_domain": true or false, "needs_account_data": true or false, "is_ambiguous": true or false, "clarifying_question": "<one short clarifying question in {language_name}, grounded only in the content preview, or null if not ambiguous>"}}

Question: {question}
Retrieved document topics: {topics}
Best-matching content preview:
{content_preview}
"""

_LANGUAGE_NAMES = {"ar": "Arabic", "en": "English"}

# How many top results' text to show the classifier, and how much of
# each -- enough for the model to judge "is this a generic, reusable
# answer" and, when genuinely ambiguous, to ground the clarifying
# question in real content instead of inventing categories. Widened
# from (2, 300) after manual testing found the model fabricating
# clarifying-question options ("a subscription", "a recurring payment")
# that did not exist anywhere in the corpus -- a narrower preview simply
# didn't show it enough of what was actually retrieved to draw from.
# Widened again from 4 to 5 (matching /ask's default top_k) after
# testing a query with 5 near-tied real answers -- with the old count of
# 4, the classifier never even saw the 5th one, so it couldn't have
# listed it in a clarifying question no matter how the prompt was worded.
_PREVIEW_CHUNK_COUNT = 5
_PREVIEW_CHARS_PER_CHUNK = 220


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
        # Pinned so the same question + same retrieved chunks always
        # yield the same guardrail decision -- previously unset, so a
        # question sitting right at the ambiguous/needs-account-data
        # boundary could flip its classification between identical runs.
        temperature=0,
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
