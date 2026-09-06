"""
Task 4: the POST /ask endpoint. Wraps the retrieval + Groq pipeline with
a real HTTP API, including streaming so an agent on a live call sees the
answer appear progressively instead of waiting silently.

Task 6: before generating a normal RAG answer, /ask runs the retrieved
chunks and the question through app/guardrails/guardrails.py's
decide_action(), which can short-circuit the request with a refusal or a
clarifying question instead -- see that module for the 6 cases handled.
"""

import os
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from groq import Groq

from app.rag.retrieval import build_context
from app.rag.language_detect import detect_language
from app.retrieval.retrieval import search as retrieval_search, vector_search
from app.guardrails.guardrails import (
    is_arabizi,
    translate_arabizi_bilingual,
    normalize_query_for_retrieval,
    merge_chunk_lists,
    decide_action,
    refusal_text,
    PREVIEW_CHUNK_COUNT,
)

app = FastAPI(title="Globitel Agent Assist API")

GROQ_MODEL = "qwen/qwen3.6-27b"

PROMPT_PATHS = {
    "en": Path("prompts/rag_answer_en.txt"),
    "ar": Path("prompts/rag_answer_ar.txt"),
}

_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def load_prompt_template(language: str) -> str:
    return PROMPT_PATHS[language].read_text(encoding="utf-8")


class AskRequest(BaseModel):
    question: str
    language: str | None = None  # optional hint: "ar" or "en"
    top_k: int | None = 5
    # Task 5: which retrieval mode to use -- "vector" (Task 4, unchanged),
    # "keyword" (BM25), or "hybrid" (vector + keyword, RRF-fused, reranked).
    # Defaults to hybrid; exposed here (not hardcoded) so the 3 modes can
    # be compared live through the same endpoint, same as hybrid-results.md.
    mode: str | None = "hybrid"


@app.post("/ask")
def ask(request: AskRequest):
    """
    Retrieves relevant chunks, builds the prompt, and streams the LLM's
    answer back as plain text. Sources, retrieved chunks, and token cost
    are sent as a final JSON line after the answer text, since usage
    stats are only known once the stream completes.
    """
    # Basic input validation -- covers the "empty question" and
    # "very long question" API test cases required by the task.
    question = request.question.strip()

    if not question:
        def empty_error():
            yield json.dumps({"error": "Question cannot be empty."}, ensure_ascii=False)
        return StreamingResponse(empty_error(), media_type="text/plain", status_code=400)

    MAX_QUESTION_CHARS = 1000
    if len(question) > MAX_QUESTION_CHARS:
        def too_long_error():
            yield json.dumps(
                {"error": f"Question too long ({len(question)} chars). Maximum is {MAX_QUESTION_CHARS}."},
                ensure_ascii=False,
            )
        return StreamingResponse(too_long_error(), media_type="text/plain", status_code=400)

    detected_language = request.language or detect_language(question)
    top_k = request.top_k or 5
    mode = request.mode or "hybrid"

    client = get_groq_client()

    # Task 6: Arabizi (Levantine Arabic typed in Latin letters/digits, e.g.
    # "kif ba3mal top up") has zero Arabic-script characters, so
    # detect_language's character-ratio check always classifies it as
    # "en" -- see language_detect.py's own test cases for that gap.
    # Override the language here, and search with BOTH an Arabic
    # transliteration AND an English translation of the question --
    # not just Arabic. Found via manual testing: some FAQ answers in this
    # corpus exist in only one language (e.g. "Does an Electronic Voucher
    # expire?" has no Arabic counterpart at all), so an Arabizi query
    # translated to Arabic only can completely miss an English-only
    # answer. Searching both and merging finds the chunk in whichever
    # language it actually exists in. The customer's original wording
    # still reaches the answering model and the response metadata
    # unchanged either way.
    # How many candidates to actually fetch from retrieval -- normally
    # just top_k, but for hybrid mode we fetch a wider pool (matching
    # guardrails.PREVIEW_CHUNK_COUNT) so the guardrail classifier below
    # can see far enough into the ranking to catch a genuinely relevant
    # chunk that plain RRF fusion (no reranker -- see retrieval.py)
    # buried outside the top few. The final answer still only uses the
    # user-requested top_k, sliced off this wider fetch below.
    fetch_top_k = PREVIEW_CHUNK_COUNT if mode == "hybrid" else top_k

    arabizi_override_applied = False
    if not request.language and is_arabizi(question):
        detected_language = "ar"
        arabizi_override_applied = True
        translations = translate_arabizi_bilingual(client, GROQ_MODEL, question)

        outcome_ar = retrieval_search(translations["arabic"], mode=mode, top_k=fetch_top_k)
        outcome_en = retrieval_search(translations["english"], mode=mode, top_k=fetch_top_k)

        merged_chunks = merge_chunk_lists(outcome_ar["results"], outcome_en["results"])[:fetch_top_k]
        retrieval_outcome = {
            "mode": mode,
            "query": question,
            "elapsed_ms": round(outcome_ar["elapsed_ms"] + outcome_en["elapsed_ms"], 2),
            "results": merged_chunks,
        }
        # Arabizi already goes through an LLM rewrite (into standard
        # Arabic AND English) via translate_arabizi_bilingual above --
        # that already IS the normalization this variable exists for, so
        # there is no separate retrieval_query for the confidence check
        # below; it builds its own variants from `translations` directly.
        retrieval_query = None
    else:
        # Normalize colloquial/regional wording to standard phrasing
        # before retrieval -- see normalize_query_for_retrieval()'s
        # docstring for why vector/keyword matching needs this help.
        # Only affects what gets embedded/matched against the corpus;
        # `question` (the customer's real wording) still reaches the
        # answering model and every response field unchanged.
        retrieval_query = normalize_query_for_retrieval(client, GROQ_MODEL, question, detected_language)
        retrieval_outcome = retrieval_search(retrieval_query, mode=mode, top_k=fetch_top_k)

    # classify_chunks: the wider pool, passed to decide_action() below so
    # classify_intent() can see past the top few. chunks: what actually
    # builds the answer's context (and gets reported as "the" retrieved
    # chunks in the response metadata).
    #
    # For hybrid mode, chunks uses the SAME wide pool as classify_chunks
    # (not sliced down to the user-requested top_k) -- manual testing
    # found a single-answer question ("كيف بقدر اعبي محفظتي؟") whose one
    # correct chunk ranked #18 in plain RRF fusion (no reranker -- see
    # retrieval.py), well past top_k=5. The classifier's wider window
    # (fix above) catches this for ambiguity detection, but the answer
    # itself would still have been generated from a context that never
    # included the right chunk at all -- a real, single answer that
    # exists in the corpus, wrongly refused as "no info" purely because
    # of where RRF happened to rank it. Non-hybrid modes (vector/keyword
    # alone) keep the original top_k slicing -- their own score is
    # already meaningful, so they don't have this "correct chunk ranked
    # low despite passing the confidence check" failure mode the same way.
    classify_chunks = retrieval_outcome["results"]
    chunks = classify_chunks if mode == "hybrid" else classify_chunks[:top_k]

    # Task 6: decide whether to refuse, ask a clarifying question, or
    # answer normally -- before spending any tokens on a full RAG answer.
    # is_arabizi_query softens the relevance threshold for this query
    # (see guardrails.ARABIZI_RELEVANCE_THRESHOLD) since the
    # transliteration step above adds noise the underlying retrieval
    # wasn't trained around, and Task 6 requires Arabizi input to still
    # be answered.
    #
    # confidence_score: on the hybrid path specifically, `chunks`' own
    # top score is rrf_score, which tune_threshold.py measured as
    # unusable for the no-info decision (see guardrails.py's note above
    # passes_relevance_threshold()) -- a genuinely relevant and a
    # genuinely irrelevant question score almost identically, since RRF
    # reflects rank position, not match strength. So for hybrid, run one
    # extra plain vector_search() here just for this confidence check
    # (top_k=1, cheap) -- vector/keyword-only modes still use `chunks`'
    # own score directly (see decide_action's confidence_score=None
    # default), since those scores already carry real magnitude.
    confidence_score = None
    if mode == "hybrid":
        # Same normalized text used for retrieval above -- checking
        # confidence against the customer's raw wording again would
        # reintroduce the exact colloquial/standard mismatch
        # normalize_query_for_retrieval() exists to fix.
        variants = [translations["arabic"], translations["english"]] if arabizi_override_applied else [retrieval_query]
        scores = []
        for variant in variants:
            v_results = vector_search(variant, top_k=1)
            if v_results and v_results[0].get("score") is not None:
                scores.append(v_results[0]["score"])
        confidence_score = max(scores) if scores else None

    decision = decide_action(
        client, GROQ_MODEL, question, detected_language, classify_chunks,
        is_arabizi_query=arabizi_override_applied,
        confidence_score=confidence_score,
    )

    if decision["action"] != "answer_normally":
        def guardrail_response():
            if decision["action"] == "ambiguous":
                text = decision["clarifying_question"]
            else:
                text = refusal_text(decision["action"], detected_language)
            yield text

            sources = sorted(set(c["source_file"] for c in chunks))
            metadata = {
                "language": detected_language,
                "retrieval_mode": mode,
                "retrieval_latency_ms": retrieval_outcome["elapsed_ms"],
                "guardrail_action": decision["action"],
                "sources": sources,
                "retrieved_chunks": chunks,
                "token_usage": {
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                },
            }
            yield "\n\n---METADATA---\n"
            yield json.dumps(metadata, ensure_ascii=False)

        return StreamingResponse(guardrail_response(), media_type="text/plain")

    context = build_context(chunks)

    template = load_prompt_template(detected_language)
    filled_prompt = template.replace("{context}", context).replace("{question}", question)

    def stream_response():
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": filled_prompt}],
            # "default" reasoning was tried as a fix for garbled Arabic
            # words (see prompts/rag_answer_*.txt rule 8), and it did
            # produce clean output -- but a live test measured ~110s per
            # answer even with reasoning_format="hidden" (the model still
            # does the full reasoning pass internally, just doesn't show
            # it), which is unusable for a live-call product. Reverted to
            # "none" -- rule 8's explicit language-purity instruction is
            # the fix being kept for the garbling problem instead.
            reasoning_effort="none",
            # Pinned low (not 0) so answers stay deterministic-ish for
            # identical questions while still reading naturally, rather
            # than at Groq's default (unset, effectively high-variance).
            temperature=0.2,
            # Groq's per-minute output-token rate limit is checked
            # against the request's max possible output, not what it
            # actually generates -- leaving this unset let Groq assume a
            # large default, which repeatedly tripped a 429
            # (RateLimitError) during testing even though the prompt
            # itself asks for 1-3 sentences. 500 comfortably covers even
            # a longer answer (e.g. a step list, or rule 7's
            # present-both-sides conflict wording).
            max_tokens=500,
            stream=True,
        )

        completion_text = ""
        prompt_tokens = None
        completion_tokens = None

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                completion_text += delta
                yield delta

            # The final chunk of a Groq stream carries x_groq.usage stats.
            if hasattr(chunk, "x_groq") and chunk.x_groq and chunk.x_groq.usage:
                prompt_tokens = chunk.x_groq.usage.prompt_tokens
                completion_tokens = chunk.x_groq.usage.completion_tokens

        sources = sorted(set(c["source_file"] for c in chunks))
        metadata = {
            "language": detected_language,
            "retrieval_mode": mode,
            "retrieval_latency_ms": retrieval_outcome["elapsed_ms"],
            "guardrail_action": "answer_normally",
            "sources": sources,
            "retrieved_chunks": chunks,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": (prompt_tokens + completion_tokens) if prompt_tokens and completion_tokens else None,
            },
        }
        yield "\n\n---METADATA---\n"
        yield json.dumps(metadata, ensure_ascii=False)

    return StreamingResponse(stream_response(), media_type="text/plain")


@app.get("/health")
def health():
    return {"status": "ok"}


# Simple browser UI over /ask -- single static file, no build step, served
# from the same origin as the API so the page's fetch() calls need no CORS
# configuration. See app/static/index.html for the frontend itself.
STATIC_DIR = Path("app/static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")