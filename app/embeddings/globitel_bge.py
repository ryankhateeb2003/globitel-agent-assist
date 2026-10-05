"""
Client for Globitel's own hosted embedding API (globitelai-bge) -- the
production embedding backend for /ask (see app/rag/retrieval.py's
EMBEDDING_BACKEND). OpenAI-compatible request/response shape, 1024-dim
vectors, already unit-normalized (verified: vector norm ~= 1.0).

Requires GLOBITEL_EMBED_API_KEY in the environment.
"""

import os

import numpy as np
import requests

from app.api.config import GLOBITEL_EMBED_API_URL, GLOBITEL_EMBED_MODEL_NAME, GLOBITEL_EMBED_BATCH_SIZE


def get_api_key() -> str:
    key = os.environ.get("GLOBITEL_EMBED_API_KEY")
    if not key:
        raise RuntimeError(
            "GLOBITEL_EMBED_API_KEY is not set -- required to use the "
            "globitelai_bge embedding backend."
        )
    return key


def embed_texts(texts: list[str], api_key: str) -> np.ndarray:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    all_vectors = []
    for start in range(0, len(texts), GLOBITEL_EMBED_BATCH_SIZE):
        batch = texts[start:start + GLOBITEL_EMBED_BATCH_SIZE]
        resp = requests.post(
            GLOBITEL_EMBED_API_URL, headers=headers,
            json={"model": GLOBITEL_EMBED_MODEL_NAME, "input": batch}, timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d["index"])
        all_vectors.extend(d["embedding"] for d in data)
    return np.array(all_vectors)
