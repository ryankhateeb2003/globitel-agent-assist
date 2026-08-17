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
    Split FAQ-style text into question + answer chunks.

    English:
        A line ending with '?' is treated as a question.

    Arabic:
        A line must:
        1. End with '?' or '؟'
        2. Start with a recognized Arabic question form.
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
        r"اين استطيع|أين أستطيع)"
    )

    for line in lines:

        if language == "ar":
            is_question = (
                line.endswith("?")
                or line.endswith("؟")
            ) and bool(
                arabic_question_pattern.match(line)
            )
        else:
            is_question = bool(
                english_question_pattern.match(line)
            )

        if is_question:
            if current:
                chunks.append(
                    "\n".join(current).strip()
                )
            current = [line]
        else:
            if current:
                current.append(line)
            else:
                current.append(line)

    if current:
        chunks.append(
            "\n".join(current).strip()
        )

    return chunks