import re


# Arabic diacritics / tashkeel
ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)


# Tatweel ـ
TATWEEL = "\u0640"


def normalize_alef(text: str) -> str:
    """
    Normalize different Alef forms to plain Alef.
    """

    return re.sub(
        r"[إأآٱ]",
        "ا",
        text,
    )


def normalize_taa_marbuta(text: str) -> str:
    """
    Normalize taa marbuta to haa.

    Example:
        خدمة -> خدمه
    """

    return text.replace("ة", "ه")


def remove_tatweel(text: str) -> str:
    """
    Remove Arabic tatweel/kashida.
    """

    return text.replace(TATWEEL, "")


def remove_diacritics(text: str) -> str:
    """
    Remove Arabic diacritics / tashkeel.
    """

    return ARABIC_DIACRITICS.sub("", text)


def normalize_arabic_digits(text: str) -> str:
    """
    Convert Arabic-Indic and Eastern Arabic-Indic digits
    to Western digits.

    Arabic-Indic:
        ٠١٢٣٤٥٦٧٨٩

    Eastern Arabic-Indic:
        ۰۱۲۳۴۵۶۷۸۹
    """

    translation_table = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789",
    )

    return text.translate(translation_table)


def normalize_whitespace(text: str) -> str:
    """
    Normalize repeated whitespace while preserving paragraphs.
    """

    lines = []

    for line in text.splitlines():

        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def normalize_arabic(text: str) -> str:
    """
    Main Arabic normalization pipeline.

    Rules:
        1. Normalize Alef variants.
        2. Normalize taa marbuta.
        3. Remove tatweel.
        4. Remove diacritics.
        5. Convert Arabic digits to Western digits.
        6. Normalize whitespace.

    This function does not change the original file.
    """

    if not isinstance(text, str):
        raise TypeError(
            "normalize_arabic() expects a string."
        )

    if not text.strip():
        return ""

    text = normalize_alef(text)

    text = normalize_taa_marbuta(text)

    text = remove_tatweel(text)

    text = remove_diacritics(text)

    text = normalize_arabic_digits(text)

    text = normalize_whitespace(text)

    return text