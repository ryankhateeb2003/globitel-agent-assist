"""
Task 4: the POST /ask endpoint. Wraps the retrieval + Groq pipeline with
a real HTTP API, including streaming so an agent on a live call sees the
answer appear progressively instead of waiting silently.
"""

import os
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq

from app.rag.retrieval import retrieve_chunks, build_context
from app.rag.language_detect import detect_language

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

    chunks = retrieve_chunks(question, top_k=top_k)
    context = build_context(chunks)

    template = load_prompt_template(detected_language)
    filled_prompt = template.replace("{context}", context).replace("{question}", question)

    client = get_groq_client()

    def stream_response():
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": filled_prompt}],
            reasoning_effort="none",
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