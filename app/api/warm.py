"""
Server startup warm-up -- runs one real hybrid search before the app
starts accepting requests, so the BM25 index (built lazily, see
keyword_search.py's _build_index()) and the default embedding backend
are already warm before the first real customer request arrives.

Without this, the FIRST /ask call after every container start paid the
full one-time model-load cost on top of its own retrieval time (observed
live: ~8.7s vs ~1.3s for the next, identical-shape request) -- a real,
user-visible slow first answer, not a fluke.

This was actually the intended design already: see
app/retrieval/eval_hybrid.py's warm_up() docstring, which assumes
"Task 4's /ask process ... loads models once at startup" -- that
assumption was just never implemented here until now.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.logs import log_warmup
from app.retrieval.retrieval import search as retrieval_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time.perf_counter()
    try:
        retrieval_search("warm up", mode="hybrid", top_k=1)
        log_warmup(success=True, elapsed_ms=(time.perf_counter() - start) * 1000)
    except Exception:
        log_warmup(success=False, elapsed_ms=(time.perf_counter() - start) * 1000)
        raise
    yield
