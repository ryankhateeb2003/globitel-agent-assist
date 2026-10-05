"""
All of /ask's StreamingResponse builders -- one function per case the
endpoint can end in (validation error, too-vague, guardrail refusal /
clarifying question, or a real generated answer). main.py just picks
which one to call; the streaming/generator mechanics live here.
"""

import json
import time

from fastapi.responses import StreamingResponse

from app.api.config import GROQ_MODEL, GENERATION_TEMPERATURE, GENERATION_MAX_TOKENS, load_prompt_template
from app.api.logs import log_timings, log_groq_error, log_tokens
from app.rag.retrieval import build_context


def empty_question_response() -> StreamingResponse:
    def gen():
        yield json.dumps({"error": "Question cannot be empty."}, ensure_ascii=False)
    return StreamingResponse(gen(), media_type="text/plain", status_code=400)


def too_long_question_response(question_length: int, max_chars: int) -> StreamingResponse:
    def gen():
        yield json.dumps(
            {"error": f"Question too long ({question_length} chars). Maximum is {max_chars}."},
            ensure_ascii=False,
        )
    return StreamingResponse(gen(), media_type="text/plain", status_code=400)


def vague_response(question: str, vague_clarify_text: dict) -> StreamingResponse:
    def gen():
        is_arabic_script = any("؀" <= c <= "ۿ" for c in question)
        text = vague_clarify_text["ar" if is_arabic_script else "en"]
        yield text
        metadata = {
            "language": "ar" if is_arabic_script else "en",
            "retrieval_mode": None,
            "retrieval_latency_ms": 0,
            "guardrail_action": "too_vague",
            "sources": [],
            "retrieved_chunks": [],
            "token_usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
        }
        yield "\n\n---METADATA---\n"
        yield json.dumps(metadata, ensure_ascii=False)
    return StreamingResponse(gen(), media_type="text/plain")


def guardrail_response(
    decision: dict, detected_language: str, mode: str, embedding_backend: str,
    retrieval_outcome: dict, chunks: list[dict], timings: dict, request_start: float,
    refusal_text_fn,
) -> StreamingResponse:
    def gen():
        if decision["action"] == "ambiguous":
            text = decision["clarifying_question"]
        else:
            text = refusal_text_fn(decision["action"], detected_language)
        yield text

        sources = sorted(set(c["source_file"] for c in chunks))
        timings["total"] = (time.perf_counter() - request_start) * 1000
        log_timings(detected_language, embedding_backend, decision["action"], timings)
        metadata = {
            "language": detected_language,
            "retrieval_mode": mode,
            "embedding_backend": embedding_backend,
            "retrieval_latency_ms": retrieval_outcome["elapsed_ms"],
            "timings_ms": timings,
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
    return StreamingResponse(gen(), media_type="text/plain")


def answer_response(
    client, question: str, detected_language: str, mode: str, embedding_backend: str,
    retrieval_outcome: dict, chunks: list[dict], timings: dict, request_start: float,
) -> StreamingResponse:
    context = build_context(chunks)
    template = load_prompt_template(detected_language)
    filled_prompt = template.replace("{context}", context).replace("{question}", question)

    def gen():
        generation_start = time.perf_counter()
        try:
            stream = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": filled_prompt}],
                # qwen3.8-27b has no reasoning_effort param (see config.py's
                # GROQ_MODEL note) -- rule 8's explicit language-purity
                # instruction in the prompt templates is what's relied on to
                # avoid garbled output now, not a reasoning setting.
                temperature=GENERATION_TEMPERATURE,
                max_tokens=GENERATION_MAX_TOKENS,
                stream=True,
            )
        except Exception as e:
            # Logged here, then re-raised unchanged -- same 500 the caller
            # got before this log line existed, just now also greppable
            # via errors.bat instead of only the raw traceback.
            log_groq_error("generation", e)
            raise

        completion_text = ""
        prompt_tokens = None
        completion_tokens = None

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                if timings["ttft"] is None:
                    timings["ttft"] = (time.perf_counter() - generation_start) * 1000
                completion_text += delta
                yield delta

            # The final chunk of a Groq stream carries x_groq.usage stats.
            if hasattr(chunk, "x_groq") and chunk.x_groq and chunk.x_groq.usage:
                prompt_tokens = chunk.x_groq.usage.prompt_tokens
                completion_tokens = chunk.x_groq.usage.completion_tokens

        timings["generation"] = (time.perf_counter() - generation_start) * 1000
        timings["total"] = (time.perf_counter() - request_start) * 1000
        log_timings(detected_language, embedding_backend, "answer_normally", timings)
        log_tokens(detected_language, prompt_tokens, completion_tokens)

        sources = sorted(set(c["source_file"] for c in chunks))
        metadata = {
            "language": detected_language,
            "retrieval_mode": mode,
            "embedding_backend": embedding_backend,
            "retrieval_latency_ms": retrieval_outcome["elapsed_ms"],
            "timings_ms": timings,
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
    return StreamingResponse(gen(), media_type="text/plain")
