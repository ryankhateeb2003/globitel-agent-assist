"""
Task 6 deliverable: tests covering all 6 hard cases, in the same
print-OK/MISMATCH-and-summarize style used by this project's other
test_*.py files (app/rag/test_language_detection.py,
app/embeddings/test_retrieval.py) -- no pytest dependency exists in
requirements.txt, so this matches the established convention rather than
introducing a new one.

Split into two groups:
  - PURE_CASES: no Groq/Qdrant needed, exercise guardrails.py's plain
    functions directly against fixed inputs -- fast, deterministic,
    always runnable.
  - INTEGRATION_CASES: exercise decide_action() end-to-end (real
    retrieval + real Groq classification call) for one example per
    required case, plus a normal-question regression check to make sure
    guardrails don't accidentally block a question Task 4 already
    answered correctly.
"""

from app.guardrails.guardrails import (
    is_arabizi,
    passes_relevance_threshold,
    refusal_text,
    top_score,
    decide_action,
)

# ---------------------------------------------------------------------
# Pure, no-network tests
# ---------------------------------------------------------------------

ARABIZI_CASES = [
    ("kif ba3mal top up la mahfazti", True),
    ("shu el code la ashoof rasidi", True),
    ("How do I top up my wallet?", False),  # clean English, no Arabizi signal
    ("كيف بقدر اعبي محفظتي؟", False),  # real Arabic script -- not Arabizi
    ("What is *140# used for?", False),  # digits present but no Latin-Arabizi words
    ("", False),
]

THRESHOLD_CASES = [
    # (results, language, is_arabizi_query, expected passes_relevance_threshold)
    ([{"rerank_score": 0.85}], "en", False, True),
    ([{"rerank_score": 0.05}], "en", False, False),
    ([], "en", False, False),
    ([{"score": 0.9}], "ar", False, True),  # falls back to "score" when no rerank_score
    # Real observed case (manual /ask test, 2026-08-18): a genuinely
    # correct top-1 match for an Arabizi-origin query scored 0.095 --
    # below the normal "ar" threshold (0.30) but above the dedicated
    # ARABIZI_RELEVANCE_THRESHOLD (0.05), so it must now pass.
    ([{"rerank_score": 0.095}], "ar", True, True),
    ([{"rerank_score": 0.095}], "ar", False, False),  # same score, NOT flagged as Arabizi -- must still fail
]


def run_pure_tests() -> tuple[int, int]:
    total = 0
    correct = 0

    print("--- is_arabizi() ---")
    for text, expected in ARABIZI_CASES:
        total += 1
        actual = is_arabizi(text)
        ok = actual == expected
        correct += ok
        print(f"[{'OK' if ok else 'MISMATCH'}] is_arabizi({text!r}) -> {actual}, expected {expected}")

    print("\n--- passes_relevance_threshold() ---")
    for results, language, is_arabizi_query, expected in THRESHOLD_CASES:
        total += 1
        actual = passes_relevance_threshold(results, language, is_arabizi_query)
        ok = actual == expected
        correct += ok
        print(f"[{'OK' if ok else 'MISMATCH'}] passes_relevance_threshold({results}, {language!r}, "
              f"is_arabizi_query={is_arabizi_query}) -> {actual}, expected {expected}")

    print("\n--- refusal_text() ---")
    for reason in ["no_info", "out_of_domain", "needs_account_data"]:
        en_text = refusal_text(reason, "en")
        ar_text = refusal_text(reason, "ar")
        for lang, text in [("en", en_text), ("ar", ar_text)]:
            total += 1
            # Both variants must exist and actually differ per language --
            # a lookup bug that silently returned the English text for
            # "ar" too would otherwise pass a bare "non-empty" check.
            ok = bool(text) and en_text != ar_text
            correct += ok
            print(f"[{'OK' if ok else 'MISMATCH'}] refusal_text({reason!r}, {lang!r}) -> {ok}")

    return correct, total


# ---------------------------------------------------------------------
# Integration tests -- need a live Groq client + Qdrant (run inside the
# Docker container, same as every other eval script in this repo)
# ---------------------------------------------------------------------

INTEGRATION_CASES = [
    ("Do you offer discounted family postpaid bundles?", "en", "no_info"),
    ("في عندكم باقة عائلية مخفضة للاشتراك الشهري؟", "ar", "no_info"),
    ("What's the weather like in Amman today?", "en", "out_of_domain"),
    ("شو الطقس بعمان اليوم؟", "ar", "out_of_domain"),
    ("How do I cancel it?", "en", "ambiguous"),
    ("كيف بلغي الاشتراك؟", "ar", "ambiguous"),
    ("Why was I charged 5 JOD last month?", "en", "needs_account_data"),
    ("ليش انخصم مني 5 دينار الشهر الماضي؟", "ar", "needs_account_data"),
    # Regression check: a normal, clearly-answerable question (Task 4's
    # own api-tests.md Test 1) must NOT be blocked by the new guardrail.
    ("What is QR Payment?", "en", "answer_normally"),
]


def run_integration_tests() -> tuple[int, int]:
    from app.api.main import get_groq_client, GROQ_MODEL
    from app.retrieval.retrieval import search as retrieval_search

    client = get_groq_client()
    total = 0
    correct = 0

    print("--- decide_action() end-to-end ---")
    for question, language, expected_action in INTEGRATION_CASES:
        total += 1
        outcome = retrieval_search(question, mode="hybrid", top_k=5)
        chunks = outcome["results"]
        decision = decide_action(client, GROQ_MODEL, question, language, chunks)
        actual_action = decision["action"]
        ok = actual_action == expected_action
        correct += ok
        print(f"[{'OK' if ok else 'MISMATCH'}] '{question[:50]}' -> {actual_action}, "
              f"expected {expected_action} (top1_score={top_score(chunks)})")

    return correct, total


if __name__ == "__main__":
    pure_correct, pure_total = run_pure_tests()
    print(f"\nPure tests: {pure_correct}/{pure_total} passed")

    try:
        int_correct, int_total = run_integration_tests()
        print(f"Integration tests: {int_correct}/{int_total} passed")
    except Exception as e:
        print(f"\n[SKIPPED] Integration tests need a live Groq client + Qdrant "
              f"(run inside the Docker app container): {e}")
