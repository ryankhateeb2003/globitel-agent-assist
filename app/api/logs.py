"""
Everything /ask writes to a log, in one place: the per-request timing
line, Groq errors, warm-up status, and per-request token counts -- so
the format of each stays consistent regardless of which code path
produced it.
"""

import json
import logging
import time
from datetime import datetime, timezone

from app.api.config import TOKEN_LOG_PATH

# uvicorn's own logger, so these lines print in the same terminal and
# format as its access log (see logs.bat / errors.bat at the repo root
# for how to watch them from a second terminal).
logger = logging.getLogger("uvicorn.error")


def log_timings(language: str, backend: str, action: str, timings: dict) -> None:
    parts = " ".join(f"{k}={v:.0f}ms" for k, v in timings.items() if v is not None)
    logger.info(f"[ask] lang={language} model={backend} action={action} {parts}")


def log_groq_error(stage: str, error: Exception) -> None:
    """
    One short, greppable line instead of the raw traceback -- the actual
    exception still propagates and prints its own traceback too (this
    doesn't change what the caller sees), this just adds a line that
    `errors.bat` can find at a glance without reading the whole stack.
    `stage` says which Groq call failed (e.g. "generation", "guardrail",
    "normalize") so a string of these in the log shows which part of the
    pipeline is actually hitting the rate limit.
    """
    logger.error(f"[groq_error] stage={stage} type={type(error).__name__} msg={error}")


def log_warmup(success: bool, elapsed_ms: float) -> None:
    status = "ok" if success else "FAILED"
    logger.info(f"[warmup] status={status} elapsed={elapsed_ms:.0f}ms")


def log_tokens(language: str, prompt_tokens: int | None, completion_tokens: int | None) -> None:
    """
    Appends one JSON line per answered question to TOKEN_LOG_PATH --
    deliberately a separate file from uvicorn's own log (not mixed in
    with [ask]/[groq_error] lines), since this is data meant to be
    loaded and aggregated later, not read line-by-line in a terminal.
    """
    if prompt_tokens is None or completion_tokens is None:
        return
    TOKEN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    with TOKEN_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
