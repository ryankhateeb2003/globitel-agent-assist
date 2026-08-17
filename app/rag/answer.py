"""
Task 4: core answer generation. Combines retrieval (Task 3's Qdrant
index) with the Groq LLM to produce a grounded, cited answer.

Detects the question's language automatically unless an explicit
language is passed in (the "optional language hint" the /ask endpoint
will expose).
"""

import os
from pathlib import Path

from groq import Groq

from app.rag.retrieval import retrieve_chunks, build_context
from app.rag.language_detect import detect_language

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
    path = PROMPT_PATHS[language]
    return path.read_text(encoding="utf-8")


def answer_question(question: str, language: str | None = None, top_k: int = 5) -> dict:
    """
    Full pipeline: detect language (unless explicitly given) -> retrieve
    -> build context -> fill prompt -> call Groq. Returns the answer plus
    the retrieved chunks and sources, ready to become the /ask endpoint's
    response body.

    language=None (default) triggers auto-detection from the question
    text. Passing an explicit "ar" or "en" overrides detection -- this is
    the "optional language hint" the /ask endpoint will expose later.
    """
    detected_language = language if language is not None else detect_language(question)

    chunks = retrieve_chunks(question, top_k=top_k)
    context = build_context(chunks)

    template = load_prompt_template(detected_language)
    filled_prompt = template.replace("{context}", context).replace("{question}", question)

    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": filled_prompt}],
        reasoning_effort="none",
    )

    answer_text = response.choices[0].message.content

    sources = sorted(set(c["source_file"] for c in chunks))

    return {
        "answer": answer_text,
        "language": detected_language,
        "sources": sources,
        "retrieved_chunks": chunks,
        "token_usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


if __name__ == "__main__":
    result = answer_question("How do I open an Orange Money wallet?")

    print("ANSWER:")
    print(result["answer"])
    print("\nDETECTED LANGUAGE:", result["language"])
    print("SOURCES:", result["sources"])
    print("TOKEN USAGE:", result["token_usage"])