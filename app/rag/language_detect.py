"""
Task 4: language detection for incoming questions.

Uses the same principle already applied in Task 1 (Arabic-character-ratio
check via Unicode range U+0600-U+06FF) rather than a new external
dependency -- keeps the approach consistent across the project and avoids
adding a language-detection library for what is, for this corpus's two
supported languages, a simple character-range check.
"""

import re

ARABIC_CHAR_PATTERN = re.compile(r"[\u0600-\u06FF]")
LATIN_CHAR_PATTERN = re.compile(r"[A-Za-z]")


def detect_language(text: str, arabic_ratio_threshold: float = 0.3) -> str:
    """
    Returns "ar" or "en" based on the ratio of Arabic characters to total
    letter characters (Arabic + Latin) in the text.

    A threshold rather than "any Arabic char = ar" is used because mixed
    input (e.g. "كيف بقدر افتح Orange Money؟") is common in this corpus's
    domain -- product names are frequently written in Latin script inside
    an otherwise Arabic sentence. Counting only letter characters (not
    digits, punctuation, or whitespace) avoids a short question like
    "*140#?" skewing the ratio meaninglessly.

    Defaults to "en" when the text has no letters at all (e.g. only
    digits/symbols) or is empty, since that is the safer fallback for an
    English-first codebase and prompt set.
    """
    if not text or not text.strip():
        return "en"

    arabic_chars = len(ARABIC_CHAR_PATTERN.findall(text))
    latin_chars = len(LATIN_CHAR_PATTERN.findall(text))
    total_letters = arabic_chars + latin_chars

    if total_letters == 0:
        return "en"

    arabic_ratio = arabic_chars / total_letters
    return "ar" if arabic_ratio >= arabic_ratio_threshold else "en"


if __name__ == "__main__":
    test_cases = [
        ("كيف بقدر افتح محفظة اورنج موني؟", "ar"),
        ("How do I open an Orange Money wallet?", "en"),
        ("كيف بقدر افتح Orange Money wallet؟", "ar"),  # mixed, mostly Arabic
        ("What is *140# used for?", "en"),  # mostly Latin, has a symbol
        ("kif ba3mal top up", "en"),  # Arabizi -- Latin letters, no Arabic script
    ]

    for text, expected in test_cases:
        detected = detect_language(text)
        status = "OK" if detected == expected else "MISMATCH"
        print(f"[{status}] '{text}' -> detected={detected}, expected={expected}")