"""
Task 5, optimization 2 of 3: a smaller/faster Groq model for "easy"
questions, reserving the larger model for harder ones.

Why this one and not parallelizing retrieval (the other common option):
measured on this project's own data (eval/task4_experiments/results/),
vector+keyword search together are 200-700ms -- under 1% of a typical
request's total time. The real cost is the 2-3 Groq calls per request
(guardrail classification + generation), which run 5,000-13,000ms each.
Parallelizing retrieval would save a few hundred ms out of tens of
thousands -- not worth it. Swapping which MODEL answers does attack the
actual bottleneck.

"Easy" is decided from `confidence_score` -- the top vector-similarity
score, already computed by main.py for the relevance-threshold check
before this module is ever called, so routing costs nothing extra to
compute.
"""

# openai/gpt-oss-20b -- already used and verified elsewhere in this
# project (it's Task 3's judge model), so it's a known-working, already
# -available choice, not a new untested dependency.
SMALL_MODEL = "openai/gpt-oss-20b"

# Calibrated against this collection's real scores (large chunks,
# globitelai_bge), not guessed -- checked live: even clearly-matching,
# simple FAQ-style questions ("How can I check my balance?", "How do I
# top up my account?") score 0.62-0.71 top similarity, never near a
# first-guess 0.75 (which would route essentially nothing). 0.65 sits
# just above that observed "clear match" range and above the normal
# pass thresholds (0.60 EN / 0.55 AR for globitelai_bge -- see
# guardrails.py's RELEVANCE_THRESHOLDS_BY_BACKEND), so it's still
# selective, not wide open. Re-check against real score distributions
# again if the chunk set or embedding backend ever changes -- this
# number is tied to both.
EASY_CONFIDENCE_THRESHOLD = 0.65


def choose_generation_model(confidence_score: float | None, main_model: str) -> str:
    """
    Returns SMALL_MODEL for a confidently-matched question, else
    main_model (the caller's normal GROQ_MODEL) unchanged. confidence_score
    being None (no hybrid-path score available) always keeps the main
    model -- never route on missing information.
    """
    if confidence_score is not None and confidence_score >= EASY_CONFIDENCE_THRESHOLD:
        return SMALL_MODEL
    return main_model
