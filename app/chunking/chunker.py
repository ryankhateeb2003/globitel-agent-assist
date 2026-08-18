from typing import List


def chunk_text(
    text: str,
    strategy: str = "fixed",
    language: str = "en"
) -> List[str]:
    """
    Main chunking interface.

    strategy:
        - fixed
        - sentence
        - structure

    language:
        - en
        - ar
    """

    if strategy == "fixed":
        return fixed_size_chunk(text)

    elif strategy == "sentence":
        return sentence_based_chunk(text)

    elif strategy == "structure":
        return structure_based_chunk(text, language=language)

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def fixed_size_chunk(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:
    """
    Split text into fixed character chunks with overlap.
    """

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        chunks.append(chunk)

        start = end - overlap

        if start < 0:
            start = 0

        if end >= text_length:
            break

    return chunks


def sentence_based_chunk(
    text: str,
    chunk_size: int = 1000
) -> list[str]:
    """
    Split text into chunks while keeping complete sentences together.
    """

    import re

    sentences = re.split(
        r'(?<=[.!?؟])\s+',
        text.strip()
    )

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if not current_chunk:
            current_chunk = sentence

        elif len(current_chunk) + 1 + len(sentence) <= chunk_size:
            current_chunk += " " + sentence

        else:
            chunks.append(current_chunk)
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def structure_based_chunk(
    text: str,
    language: str = "en"
) -> list[str]:
    """
    Split FAQ-style text into question + answer chunks, keeping each
    question with its answer.

    English:
        A line ending with '?' is treated as a question.

    Arabic:
        A line must:
        1. End with '?' or '؟'
        2. Start with a recognized Arabic question form.

    Not every section in this corpus is phrased as a question -- pages like
    mobile-lines.html mix FAQ pairs with plain feature headings (e.g.
    "Always-on data feature"). Without also splitting on those, every
    heading after the first question in a block gets glued onto that
    question's chunk, producing oversized chunks that mix unrelated
    topics. _is_section_heading() below detects that case (a short,
    unpunctuated title line, not an instruction, followed by a real
    sentence) so it becomes its own split point too, alongside questions.
    """

    import re

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    chunks = []
    current = []

    english_question_pattern = re.compile(
        r"^.*\?$"
    )

    arabic_question_pattern = re.compile(
        r"^(كيف|هل|مين|من|ما|ماذا|متى|أين|اين|وين|كم|شو|لماذا|ليش|ليه|"
        r"بقدر|هل يمكن|يمكنني|هل يستطيع|هل تستطيع|ما هي|ما هو|"
        r"ماذا يحدث|ماذا افعل|ماذا أفعل|من يستطيع|من يمكنه|"
        r"اين استطيع|أين أستطيع|في اي|في أي)"
    )

    def is_question(line: str) -> bool:
        if language == "ar":
            return (
                line.endswith("?") or line.endswith("؟")
            ) and bool(arabic_question_pattern.match(line))
        return bool(english_question_pattern.match(line))

    is_arabic_line = lambda s: any("؀" <= c <= "ۿ" for c in s)

    _IMPERATIVE_WORDS = {
        "اضغط", "ادخل", "اختر", "قم", "انشئ", "حمل", "سجل", "افتح", "ثم",
        "press", "click", "select", "enter", "open", "download", "create",
        "tap", "then", "choose", "go", "visit", "fill", "add", "confirm",
    }
    _YES_NO_LINES = {"نعم", "لا", "Yes", "No", "yes", "no"}
    _AR_CONNECTOR_PREFIXES = ("ل", "و", "ف", "ب", "ك")
    _EN_CONNECTOR_WORDS = {
        "to", "for", "this", "that", "these", "those", "and", "or",
        "with", "the",
    }

    def is_section_heading(line: str, prev_line: str | None, next_line: str | None) -> bool:
        """
        A standalone section title that introduces a new topic without
        being phrased as a question, e.g. "Always-on data feature".
        Requires: short, no closing punctuation, the previous line already
        ended its own sentence (or there is none), not an instruction step
        or a yes/no line, not a sentence continuation (comma or connector
        word), and is immediately followed by a real sentence -- the same
        signal a human uses to spot a heading versus a stray short line.
        """
        if len(line) < 3 or len(line) > 50:
            return False
        if line.endswith((".", "?", "؟", ":", ",", "،")):
            return False
        if next_line is None:
            return False
        # If the previous line hasn't closed its own sentence (no ., ?, ؟),
        # this line is a continuation/wrapped fragment of it, not a new
        # heading. This is deliberately strict: it also blocks some real
        # headings that happen to follow an unpunctuated paragraph, but a
        # looser "does the previous line dangle on a connector word" check
        # was tried and let stray mid-sentence fragments (e.g. a short code
        # at the end of an instruction) split away from the sentence they
        # belong to -- worse than missing a few headings.
        if prev_line is not None and not prev_line.endswith((".", "?", "؟")):
            return False
        # If the previous line is itself a recognized question, this line
        # is the start of that question's answer, not a new heading --
        # even a short factual answer (e.g. "Aero Mobile", "Dial *976#")
        # looks structurally identical to a heading otherwise.
        if prev_line is not None and is_question(prev_line):
            return False

        words = line.lower().split()
        if not words:
            return False
        if any(w.strip("().,") in _IMPERATIVE_WORDS for w in words[:3]):
            return False
        if line.strip("،, ") in _YES_NO_LINES:
            return False
        if "," in line or "،" in line:
            return False

        first_word = words[0]
        if is_arabic_line(line) and first_word[:1] in _AR_CONNECTOR_PREFIXES and len(first_word) <= 8:
            return False
        if not is_arabic_line(line) and first_word in _EN_CONNECTOR_WORDS:
            return False

        next_stripped = next_line.strip()
        is_real_sentence_after = (
            len(next_stripped) >= len(line) * 1.8
            and next_stripped.endswith((".", "?", "؟", ")"))
        )
        if not is_real_sentence_after:
            return False

        if len(words) >= 5:
            return False

        return True

    for i, line in enumerate(lines):
        prev_line = lines[i - 1] if i > 0 else None
        next_line = lines[i + 1] if i + 1 < len(lines) else None

        is_split_point = is_question(line) or is_section_heading(line, prev_line, next_line)

        if is_split_point:
            if current:
                chunks.append(
                    "\n".join(current).strip()
                )
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append(
            "\n".join(current).strip()
        )

    return chunks