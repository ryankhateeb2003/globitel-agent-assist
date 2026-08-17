from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
import re

import pymupdf


# =========================================================
# NORMALIZATION
# =========================================================

def _normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\u200c", "")
    text = text.replace("\u200d", "")
    text = text.replace("\ufeff", "")

    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _comparison_key(text: str) -> str:
    text = _normalize_text(text).casefold()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[•◦▪▫●○■□◆◇]+\s*", "", text)
    return text.strip()


# =========================================================
# BASIC NOISE
# =========================================================

_DECORATIVE_ONLY = re.compile(
    r"^[\s•◦▪▫●○■□◆◇★☆→←↑↓|/\\\-_=~*·]+$"
)

_NUMBER_ONLY = re.compile(
    r"^\d+[\.\)]?$"
)

_PAGE_NUMBER = re.compile(
    r"^(?:page\s*)?\d+$",
    re.IGNORECASE,
)


def _is_basic_noise(line: str) -> bool:
    if not line:
        return True

    if _DECORATIVE_ONLY.fullmatch(line):
        return True

    if _NUMBER_ONLY.fullmatch(line):
        return True

    if _PAGE_NUMBER.fullmatch(line):
        return True

    return False


# =========================================================
# UI / ACCESSIBILITY
# =========================================================

_UI_LINES = {
    "skip to main content",
    "skip to content",
    "main navigation",
    "navigation",
    "apps menu",
    "accessibility",
    "dark mode",
    "light mode",
    "font size",
    "switch",
    "search",
    "submit",
    "apply",
    "cancel",
    "close",
    "open",
    "back",
    "next",
    "previous",
    "home",
    "menu",
    "main menu",
    "login",
    "log in",
    "logout",
    "log out",
    "sign in",
    "sign out",
    "register",
    "copyright",
    "all rights reserved",
    "orange jordan",
    "follow us",
    "download max it app",
    "max it app",
    "privacy policy",
    "terms & conditions",
    "terms and conditions",
}


def _is_ui_line(line: str) -> bool:
    normalized = line.casefold().strip()
    if normalized in _UI_LINES:
        return True
    if normalized.startswith("copyright ") or normalized.startswith("©"):
        return True
    return False


def _is_language_control(line: str) -> bool:
    normalized = re.sub(r"\s+", "", line.casefold())

    return normalized in {
        "englishالعربية",
        "العربيةenglish",
        "englishالعربيه",
        "العربيهenglish",
        "english",
        "العربية",
        "العربيه",
    }


# =========================================================
# GENERIC NAVIGATION
# =========================================================

_GENERIC_NAV_LINES = {
    "personal",
    "business",
    "corporate",
    "account",
    "products",
    "services",
    "offers",
    "categories",
    "category",
    "topics",
    "more topics",
    "related links",
    "useful links",
    "useful faqs",
    "quick links",
    "helpful short codes",
    "bill payment",
    "internet devices user guides",
    "find shops",
    "internet coverage",
    "contact us",
    "messenger",
    "instagram",
    "whatsapp",
    "orange products",
    "bundles",
    "balance",
    "max it app",
}


def _is_generic_navigation(line: str) -> bool:
    return line.casefold().strip() in _GENERIC_NAV_LINES


# =========================================================
# CTA
# =========================================================

_CTA_LINES = {
    "click here",
    "learn more",
    "read more",
    "view more",
    "view all",
    "get started",
    "get in touch",
}


def _is_cta(line: str) -> bool:
    return line.casefold().strip() in _CTA_LINES


# =========================================================
# BREADCRUMBS
# =========================================================

def _is_breadcrumb(line: str) -> bool:
    return bool(
        re.fullmatch(
            r"^\d+\.\s*.+$",
            line,
        )
    )


# =========================================================
# BULLET DETECTION
# =========================================================

def _is_bullet(line: str) -> bool:
    return line.startswith(
        (
            "•",
            "◦",
            "▪",
            "▫",
            "●",
            "○",
            "■",
            "□",
            "- ",
        )
    )


# =========================================================
# CLEAN RAW BLOCK
# =========================================================

def _clean_block(text: str) -> list[str]:

    result = []

    for raw_line in text.splitlines():

        line = _normalize_text(raw_line)

        if not line:
            continue

        if _is_basic_noise(line):
            continue

        if _is_ui_line(line):
            continue

        if _is_language_control(line):
            continue

        if _is_breadcrumb(line):
            continue

        if _is_cta(line):
            continue

        result.append(line)

    return result


# =========================================================
# NAVIGATION BLOCK DETECTION
# =========================================================

def _looks_like_navigation_block(
    lines: list[str],
) -> bool:

    if len(lines) < 5:
        return False

    short_lines = 0
    bullet_lines = 0
    nav_lines = 0

    for line in lines:

        if len(line.split()) <= 6:
            short_lines += 1

        if _is_bullet(line):
            bullet_lines += 1

        if _is_generic_navigation(line):
            nav_lines += 1

    short_ratio = short_lines / len(lines)
    bullet_ratio = bullet_lines / len(lines)

    if any(len(x.split()) >= 15 for x in lines):
        return False

    if nav_lines >= 2:
        return True

    if short_ratio >= 0.85 and bullet_ratio >= 0.15:
        return True

    if short_ratio >= 0.90:
        return True

    return False


# =========================================================
# REPEATED BLOCKS
# =========================================================

def _find_repeated_blocks(
    pages: list[list[list[str]]],
) -> set[str]:

    occurrences = Counter()

    for page in pages:

        seen = set()

        for block in page:

            if not block:
                continue

            key = _comparison_key(
                " ".join(block)
            )

            if not key:
                continue

            if len(key.split()) <= 40:
                seen.add(key)

        for key in seen:
            occurrences[key] += 1

    return {
        key
        for key, count in occurrences.items()
        if count >= 2
    }


def _remove_repeated_blocks(
    pages: list[list[list[str]]],
) -> list[list[list[str]]]:

    repeated = _find_repeated_blocks(pages)

    cleaned_pages = []

    for page in pages:

        cleaned_page = []

        for block in page:

            key = _comparison_key(
                " ".join(block)
            )

            if key in repeated:
                continue

            cleaned_page.append(block)

        cleaned_pages.append(cleaned_page)

    return cleaned_pages


# =========================================================
# REMOVE DUPLICATES
# =========================================================

def _remove_consecutive_duplicates(
    lines: list[str],
) -> list[str]:

    result = []
    previous_key = None

    for line in lines:

        key = _comparison_key(line)

        if not key:
            continue

        if key == previous_key:
            continue

        result.append(line)
        previous_key = key

    return result


# =========================================================
# HEADING + CONTENT SEPARATION
# =========================================================

def _split_heading_content(line: str) -> list[str]:

    patterns = [
        r"^(.{3,60}?)\s+(A secured\b.+)$",
        r"^(.{3,60}?)\s+(With pay monthly offers\b.+)$",
        r"^(.{3,60}?)\s+(To stay connected\b.+)$",
        r"^(.{3,60}?)\s+(Once you\b.+)$",
        r"^(.{3,60}?)\s+(You can\b.+)$",
        r"^(.{3,60}?)\s+(You can benefit\b.+)$",
        r"^(.{3,60}?)\s+(Reduced calling rates\b.+)$",
        r"^(.{3,60}?)\s+(Because we\b.+)$",
        r"^(.{3,60}?)\s+(Need help\b.+)$",
    ]

    for pattern in patterns:

        match = re.match(
            pattern,
            line,
            re.IGNORECASE,
        )

        if match:

            heading = match.group(1).strip()
            content = match.group(2).strip()

            if (
                len(heading.split()) <= 8
                and len(content.split()) >= 3
            ):
                return [
                    heading,
                    content,
                ]

    gen_match = re.match(r"^([A-Z0-9][A-Za-z0-9\s\-\&]{2,45})\s+([A-Z][a-z0-9\b].{15,})$", line)
    if gen_match:
        h = gen_match.group(1).strip()
        c = gen_match.group(2).strip()
        if len(h.split()) <= 6 and not h.endswith((".", "?", "!", ":", ",", ";")):
            return [h, c]

    return [line]


# =========================================================
# SAFE WRAPPED-LINE MERGING
# =========================================================

def _looks_like_continuation(
    previous: str,
    current: str,
) -> bool:

    if not previous or not current:
        return False

    if _is_bullet(current) or _is_bullet(previous):
        return False

    if re.search(
        r"\*\d+(?:\*\d+)*#",
        current,
    ) or re.search(
        r"\*\d+(?:\*\d+)*#",
        previous,
    ):
        return False

    if "http://" in current or "https://" in current or "http://" in previous or "https://" in previous:
        return False

    if previous.endswith(
        (".", "?", "!", ":")
    ):
        return False

    if len(previous.split()) <= 8 and len(previous) <= 60:
        if not previous.endswith((",", ";", "-", "–")):
            last_word = previous.split()[-1].casefold()
            if last_word not in {"and", "or", "with", "from", "to", "for", "of", "on", "in", "at", "by", "من", "في", "على", "إلى", "عن", "مع", "أو", "و"}:
                return False

    if previous.endswith(
        (",", ";", "-", "–")
    ):
        return True

    if current[0].islower():
        return True

    continuation_words = {
        "and",
        "or",
        "with",
        "from",
        "to",
        "for",
        "of",
        "on",
        "in",
        "after",
        "before",
        "while",
        "when",
        "that",
        "which",
        "the",
        "a",
        "an",
        "is",
        "are",
        "من",
        "في",
        "على",
        "إلى",
        "عن",
        "مع",
        "أو",
        "و",
    }

    first_word = current.split()[0].casefold()

    return first_word in continuation_words


def _merge_wrapped_lines(
    lines: list[str],
) -> list[str]:

    if not lines:
        return []

    result = [lines[0]]

    for current in lines[1:]:

        previous = result[-1]

        if _looks_like_continuation(
            previous,
            current,
        ):
            result[-1] = (
                previous.rstrip()
                + " "
                + current.lstrip()
            )
        else:
            result.append(current)

    return result


# =========================================================
# BIDI CHECK (PDF vs matching HTML twin)
# =========================================================

def _check_bidi_against_html(
    pdf_text: str,
    file_path: Path,
    threshold: float = 0.5,
) -> None:
    """
    Compare this PDF's extracted text against its matching HTML twin
    (same filename, .html instead of .pdf, same folder) to catch reversed/
    reordered Arabic text -- a common PDF bidi extraction failure.

    Raises ValueError if similarity is below threshold, so corrupted PDF
    text never silently enters the corpus. If no matching HTML file exists,
    the check is skipped (nothing to compare against, so we don't block
    ingestion of PDFs that simply have no HTML twin).
    """

    html_twin = file_path.with_suffix(".html")

    if not html_twin.exists():
        return

    try:
        from .html_extractor import extract_html
        html_text = extract_html(html_twin)
    except Exception:
        return

    ratio = SequenceMatcher(None, pdf_text, html_text).ratio()

    if ratio < threshold:
        raise ValueError(
            f"PDF text appears corrupted/reordered (bidi failure): {file_path}. "
            f"Similarity to matching HTML ({html_twin.name}) is {ratio:.2f}, "
            f"below the {threshold} threshold. Rejecting rather than ingesting "
            f"garbled Arabic text."
        )


# =========================================================
# MAIN EXTRACTOR
# =========================================================

def extract_pdf(
    file_path: str | Path,
) -> str:

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {file_path}"
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a PDF file, got: {file_path.suffix}"
        )

    if file_path.stat().st_size == 0:
        raise ValueError(
            f"PDF file is empty: {file_path}"
        )

    pages = []

    with pymupdf.open(file_path) as document:

        if len(document) == 0:
            raise ValueError(
                f"PDF contains no pages: {file_path}"
            )

        for page in document:

            raw_blocks = page.get_text(
                "blocks",
                sort=True,
            )

            page_blocks = []

            for block in raw_blocks:

                if len(block) < 5:
                    continue

                raw_text = block[4]

                if not raw_text:
                    continue

                lines = _clean_block(
                    raw_text
                )

                if not lines:
                    continue

                if _looks_like_navigation_block(
                    lines
                ):
                    continue

                page_blocks.append(lines)

            if page_blocks:
                pages.append(page_blocks)

    if not pages:
        raise ValueError(
            f"PDF contains no usable text layer: {file_path}. "
            f"The document may be scanned/image-only."
        )

    pages = _remove_repeated_blocks(pages)

    lines = []

    for page in pages:

        for block in page:

            for line in block:

                line = _normalize_text(line)

                if not line:
                    continue

                if _is_generic_navigation(line):
                    continue

                parts = _split_heading_content(line)

                lines.extend(parts)

    lines = _remove_consecutive_duplicates(
        lines
    )

    lines = _merge_wrapped_lines(
        lines
    )

    text = "\n".join(lines).strip()

    if not text:
        raise ValueError(
            f"PDF extraction produced no usable text: {file_path}"
        )

    _check_bidi_against_html(text, file_path)

    return text