"""
Task 4: the POST /ask endpoint. Wraps the retrieval + Groq pipeline with
a real HTTP API, including streaming so an agent on a live call sees the
answer appear progressively instead of waiting silently.

Task 6: before generating a normal RAG answer, /ask runs the retrieved
chunks and the question through app/guardrails/guardrails.py's
decide_action(), which can short-circuit the request with a refusal or a
clarifying question instead -- see that module for the 6 cases handled.

Settings live in config.py, the startup warm-up in warm.py, the timing
log line in logs.py, and every StreamingResponse builder in stream.py --
this file just orchestrates: validate, detect language, retrieve, decide,
then hand off to the right stream.py builder.
"""

import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq

from app.api.config import GROQ_MODEL, MAX_QUESTION_CHARS, STATIC_DIR, EMBEDDING_BACKEND_DEFAULT
from app.api.warm import lifespan
from app.api import stream
from app.rag.language_detect import detect_language
from app.retrieval.retrieval import search as retrieval_search
from app.guardrails.guardrails import (
    is_arabizi,
    translate_arabizi_bilingual,
    normalize_query_for_retrieval,
    merge_chunk_lists,
    decide_action,
    refusal_text,
    is_too_vague,
    VAGUE_CLARIFY_TEXT,
    PREVIEW_CHUNK_COUNT,
)

app = FastAPI(title="Globitel Agent Assist API", lifespan=lifespan)

_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


class AskRequest(BaseModel):
    question: str
    language: str | None = None  # optional hint: "ar" or "en"
    top_k: int | None = 5
    # Task 5: which retrieval mode to use -- "vector" (Task 4, unchanged),
    # "keyword" (BM25), or "hybrid" (vector + keyword, RRF-fused, reranked).
    # Defaults to hybrid; exposed here (not hardcoded) so the 3 modes can
    # be compared live through the same endpoint, same as hybrid-results.md.
    mode: str | None = "hybrid"
    # Which embedding model to use for the vector half of retrieval --
    # "globitelai_bge" (Globitel's hosted API, the default when omitted) or
    # "bge_m3" (local) -- see app/rag/retrieval.py. The UI omits it; kept
    # so eval scripts can still compare the two per request.
    embedding_backend: str | None = None


@app.post("/ask")
def ask(request: AskRequest):
    """
    Retrieves relevant chunks, builds the prompt, and streams the LLM's
    answer back as plain text. Sources, retrieved chunks, and token cost
    are sent as a final JSON line after the answer text, since usage
    stats are only known once the stream completes.
    """
    request_start = time.perf_counter()

    # Basic input validation -- covers the "empty question" and
    # "very long question" API test cases required by the task.
    question = request.question.strip()

    if not question:
        return stream.empty_question_response()

    if len(question) > MAX_QUESTION_CHARS:
        return stream.too_long_question_response(len(question), MAX_QUESTION_CHARS)

    # Short-circuits before retrieval/classify_intent even run -- neither
    # can produce a meaningful result from input with no real content
    # (a stray character, punctuation/digits only, or one letter
    # repeated), and letting it through previously produced a
    # confusing, specific-sounding but nonsensical clarifying question
    # (see guardrails.is_too_vague's docstring for the live case found).
    if is_too_vague(question):
        return stream.vague_response(question, VAGUE_CLARIFY_TEXT)

    detected_language = request.language or detect_language(question)
    top_k = request.top_k or 5
    mode = request.mode or "hybrid"
    embedding_backend = request.embedding_backend or EMBEDDING_BACKEND_DEFAULT

    client = get_groq_client()

    # Per-stage wall-clock times for this request, logged to the terminal
    # and returned in the metadata as timings_ms. None = stage didn't run.
    timings = {
        "normalize": None, "vector": None, "keyword": None, "retrieval": None,
        "guardrail": None, "ttft": None, "generation": None, "total": None,
    }

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
        t0 = time.perf_counter()
        translations = translate_arabizi_bilingual(client, GROQ_MODEL, question)
        timings["normalize"] = (time.perf_counter() - t0) * 1000

        outcome_ar = retrieval_search(translations["arabic"], mode=mode, top_k=fetch_top_k, embedding_backend=embedding_backend)
        outcome_en = retrieval_search(translations["english"], mode=mode, top_k=fetch_top_k, embedding_backend=embedding_backend)
        outcomes = [outcome_ar, outcome_en]

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
        t0 = time.perf_counter()
        retrieval_query = normalize_query_for_retrieval(client, GROQ_MODEL, question, detected_language)
        timings["normalize"] = (time.perf_counter() - t0) * 1000
        retrieval_outcome = retrieval_search(retrieval_query, mode=mode, top_k=fetch_top_k, embedding_backend=embedding_backend)
        outcomes = [retrieval_outcome]

    timings["retrieval"] = retrieval_outcome["elapsed_ms"]
    if mode == "hybrid":
        timings["vector"] = sum(o["vector_ms"] for o in outcomes)
        timings["keyword"] = sum(o["keyword_ms"] for o in outcomes)

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
    # reflects rank position, not match strength. So for hybrid, use the
    # top cosine score of hybrid's own vector half (same normalized query,
    # same embedding model -- no second embedding call needed) --
    # vector/keyword-only modes still use `chunks`' own score directly
    # (see decide_action's confidence_score=None default), since those
    # scores already carry real magnitude.
    confidence_score = None
    if mode == "hybrid":
        scores = [o["vector_top_score"] for o in outcomes if o.get("vector_top_score") is not None]
        confidence_score = max(scores) if scores else None

    t0 = time.perf_counter()
    decision = decide_action(
        client, GROQ_MODEL, question, detected_language, classify_chunks,
        is_arabizi_query=arabizi_override_applied,
        confidence_score=confidence_score,
        embedding_backend=embedding_backend,
    )
    timings["guardrail"] = (time.perf_counter() - t0) * 1000

    if decision["action"] != "answer_normally":
        return stream.guardrail_response(
            decision, detected_language, mode, embedding_backend,
            retrieval_outcome, chunks, timings, request_start, refusal_text,
        )

    return stream.answer_response(
        client, question, detected_language, mode, embedding_backend,
        retrieval_outcome, chunks, timings, request_start,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
