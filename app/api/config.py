"""
All tunable settings for the /ask API in one place -- model names, prompt
paths, limits -- so changing a setting means editing this file, not
hunting through main.py/stream.py/warm.py.
"""

from pathlib import Path

from app.rag.retrieval import EMBEDDING_BACKEND as EMBEDDING_BACKEND_DEFAULT

GROQ_MODEL = "qwen/qwen3.8-27b"
# qwen/qwen3.6-27b was withdrawn by Groq (a preview model, pulled with no
# formal deprecation notice -- confirmed live via 404s on every call and
# its absence from client.models.list(), first observed ~2026-09-15).
# qwen3.8-27b is the closest available successor: same family/size,
# already verified in this project as the Task 3 judge model. Unlike
# 3.6, it does NOT accept reasoning_effort (a live test showed passing it
# returns empty content) -- no call in this API passes that parameter.

PROMPT_PATHS = {
    "en": Path("prompts/rag_answer_en.txt"),
    "ar": Path("prompts/rag_answer_ar.txt"),
}

# Basic input validation limit -- covers the "very long question" API
# test case required by the task.
MAX_QUESTION_CHARS = 1000


def load_prompt_template(language: str) -> str:
    return PROMPT_PATHS[language].read_text(encoding="utf-8")

# Generation call settings (Groq chat.completions.create).
GENERATION_TEMPERATURE = 0.2
# Pinned low (not 0) so answers stay deterministic-ish for identical
# questions while still reading naturally, rather than at Groq's default
# (unset, effectively high-variance).
GENERATION_MAX_TOKENS = 500
# Groq's per-minute output-token rate limit is checked against the
# request's max possible output, not what it actually generates --
# leaving this unset let Groq assume a large default, which repeatedly
# tripped a 429 (RateLimitError) during testing even though the prompt
# itself asks for 1-3 sentences. 500 comfortably covers even a longer
# answer (e.g. a step list, or a present-both-sides conflict wording).

# Per-request token counts (prompt + completion), one JSON line per
# answered question, split by language.
TOKEN_LOG_PATH = Path("logs/tokens.jsonl")

# Simple browser UI over /ask -- single static file, no build step,
# served from the same origin as the API so the page's fetch() calls
# need no CORS configuration. See app/static/index.html for the frontend.
STATIC_DIR = Path("app/static")

# Globitel's own hosted embedding API (globitelai-bge) -- the production
# embedding backend for /ask's vector search (app/embeddings/globitel_bge.py).
# OpenAI-compatible request/response shape, 1024-dim vectors. The API key
# itself is NOT here -- it stays in the GLOBITEL_EMBED_API_KEY environment
# variable, never committed to the repo.
GLOBITEL_EMBED_API_URL = "https://services.globitel.com:55200/embeddings/v1/embeddings"
GLOBITEL_EMBED_MODEL_NAME = "globitelai-bge"
GLOBITEL_EMBED_BATCH_SIZE = 32
