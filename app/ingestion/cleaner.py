import re


# =========================================================
# Generic UI / Navigation
# =========================================================

UI_EXACT_LINES = {
    "home",
    "menu",
    "main menu",
    "main navigation",
    "navigation",
    "apps menu",
    "search",
    "submit",
    "apply",
    "cancel",
    "close",
    "open",
    "back",
    "next",
    "previous",
    "login",
    "log in",
    "logout",
    "log out",
    "sign in",
    "sign out",
    "register",
    "accessibility",
    "dark mode",
    "light mode",
    "font size",
    "share",
    "print",
    "download",
    "copy",
    "language",
    "switch",
    "account",
    "contact us",
    "contact us now",
    "useful links",
    "related links",
    "quick links",
    "more topics",
    "more services",
    "watch video",
    "الرئيسية",
    "الصفحة الرئيسية",
    "القائمة",
    "القائمة الرئيسية",
    "بحث",
    "البحث",
    "إرسال",
    "تأكيد",
    "إلغاء",
    "إغلاق",
    "رجوع",
    "التالي",
    "السابق",
    "تسجيل الدخول",
    "تسجيل خروج",
    "إنشاء حساب",
    "تواصل معنا",
    "اتصل بنا",
    "تغيير اللغة",
    "مشاركة",
    "طباعة",
    "تنزيل",
    "نسخ",
    "الحساب",
    "روابط مفيدة",
    "مواضيع ذات صلة",
    "روابط سريعة",
    "المزيد من الخدمات",
    "جميع الحقوق محفوظة",
}


# =========================================================
# Generic UI patterns
# =========================================================

UI_PATTERNS = [
    r"^skip to (main )?content$",
    r"^skip to navigation$",
    r"^back to top$",
    r"^toggle (menu|navigation)$",
    r"^open (menu|navigation)$",
    r"^close (menu|navigation)$",
    r"^show (more|less)$",
    r"^load more$",
    r"^view (all|more)$",
    r"^read more$",
    r"^click here$",
    r"^learn more$",
    r"^go back$",
]


# =========================================================
# Generic CTA / boilerplate
# =========================================================

CTA_PATTERNS = [
    r"^contact us$",
    r"^contact us (now|today).*$",
    r"^get in touch.*$",
    r"^need help.*$",
    r"^how can we help.*$",
    r"^we('re| are) here to help.*$",
]


# =========================================================
# Generic navigation labels
# =========================================================

NAVIGATION_PATTERNS = [
    r"^(personal|business|corporate)$",
    r"^(products|services|offers|solutions)$",
    r"^(categories|category|topics)$",
    r"^(related links|useful links|quick links)$",
    r"^(more topics|more services)$",
    r"^(apps menu)$",
]


# =========================================================
# Common extraction artifacts
# =========================================================

ARTIFACT_LINES = {
    "a-",
    "a+",
    "switch",
    "accessibility",
    "dark mode",
    "light mode",
    "font size",
    "watch video",
    "image",
    "images",
    "icon",
    "icons",
    "breadcrumb",
    "breadcrumbs",
}


# =========================================================
# Decorative-only lines
# =========================================================

DECORATIVE_PATTERN = re.compile(
    r"^[\s•◦▪▫●○■□◆◇★☆→←↑↓|/\\\-_=~*·]+$"
)


# =========================================================
# Isolated numbering
# =========================================================

NUMBER_ONLY_PATTERN = re.compile(
    r"^\d{1,4}[\.\)]?$"
)


# =========================================================
# Whitespace normalization
# =========================================================

def _normalize_line(line: str) -> str:
    """
    Normalize whitespace without changing actual content.
    """

    line = line.replace("\xa0", " ")
    line = line.replace("\u200b", "")
    line = line.replace("\ufeff", "")

    line = re.sub(r"[ \t]+", " ", line)

    return line.strip()


# =========================================================
# Case-insensitive comparison key
# =========================================================

def _key(line: str) -> str:
    """
    Used only for comparisons.

    Example:
        Mobile Lines
        mobile lines
        MOBILE LINES

    are considered equal for duplicate detection.
    """

    return re.sub(
        r"\s+",
        " ",
        line.strip().casefold(),
    )


# =========================================================
# UI detection
# =========================================================

def _is_ui_line(line: str) -> bool:
    normalized = _key(line)

    if normalized in UI_EXACT_LINES:
        return True

    for pattern in UI_PATTERNS:
        if re.fullmatch(pattern, normalized):
            return True

    return False


# =========================================================
# CTA detection
# =========================================================

def _is_cta_line(line: str) -> bool:
    normalized = _key(line)

    for pattern in CTA_PATTERNS:
        if re.fullmatch(pattern, normalized):
            return True

    return False


# =========================================================
# Navigation detection
# =========================================================

def _is_navigation_line(line: str) -> bool:
    normalized = _key(line)

    for pattern in NAVIGATION_PATTERNS:
        if re.fullmatch(pattern, normalized):
            return True

    return False


# =========================================================
# Artifact detection
# =========================================================

def _is_artifact_line(line: str) -> bool:
    return _key(line) in ARTIFACT_LINES


# =========================================================
# Decorative detection
# =========================================================

def _is_decorative_line(line: str) -> bool:
    return bool(
        DECORATIVE_PATTERN.fullmatch(line)
    )


# =========================================================
# Number-only detection
# =========================================================

def _is_number_only_line(line: str) -> bool:
    return bool(
        NUMBER_ONLY_PATTERN.fullmatch(line)
    )


# =========================================================
# Remove consecutive duplicates
# =========================================================

def _remove_consecutive_duplicates(
    lines: list[str],
) -> list[str]:

    result = []
    previous = None

    for line in lines:

        current = _key(line)

        if current == previous:
            continue

        result.append(line)
        previous = current

    return result


# =========================================================
# Remove repeated short lines
# =========================================================

def _remove_repeated_short_lines(
    lines: list[str],
) -> list[str]:
    """
    Removes repeated short headings / navigation-like labels
    regardless of capitalization.

    Long paragraphs are NOT globally deduplicated.
    """

    result = []
    seen = set()

    for line in lines:

        normalized = _key(line)

        # Only apply global duplicate filtering to short lines.
        if len(line) <= 100:

            if normalized in seen:
                continue

            seen.add(normalized)

        result.append(line)

    return result


# =========================================================
# Main cleaner
# =========================================================

def clean_text(text: str) -> str:
    """
    Generic cleaner for:

        HTML
        DOCX
        PDF

    Removes generic:

        - navigation
        - menus
        - UI controls
        - accessibility controls
        - CTA boilerplate
        - decorative symbols
        - isolated page/navigation numbers
        - extraction artifacts
        - duplicate short headings
        - consecutive duplicates

    Preserves:

        - documentation content
        - headings
        - questions
        - answers
        - instructions
        - lists
        - URLs
        - phone numbers
        - USSD codes
        - prices
        - dates
        - technical values
        - product/service information

    The rules are NOT tied to Orange or any specific file.
    """

    if not isinstance(text, str):
        raise TypeError(
            "text must be a string"
        )

    if not text.strip():
        raise ValueError(
            "Cannot clean empty text"
        )

    cleaned_lines = []

    # =====================================================
    # First pass
    # =====================================================

    for raw_line in text.splitlines():

        line = _normalize_line(raw_line)

        if not line:
            continue

        # ---------------------------------------------
        # Decorative noise
        # ---------------------------------------------

        if _is_decorative_line(line):
            continue

        # ---------------------------------------------
        # Isolated numbers
        # ---------------------------------------------

        if _is_number_only_line(line):
            continue

        # ---------------------------------------------
        # UI
        # ---------------------------------------------

        if _is_ui_line(line):
            continue

        # ---------------------------------------------
        # Navigation
        # ---------------------------------------------

        if _is_navigation_line(line):
            continue

        # ---------------------------------------------
        # CTA boilerplate
        # ---------------------------------------------

        if _is_cta_line(line):
            continue

        # ---------------------------------------------
        # Extraction artifacts
        # ---------------------------------------------

        if _is_artifact_line(line):
            continue

        # ---------------------------------------------
        # Preserve real content
        # ---------------------------------------------

        cleaned_lines.append(line)

    # =====================================================
    # Remove immediately repeated lines
    # =====================================================

    cleaned_lines = _remove_consecutive_duplicates(
        cleaned_lines
    )

    # =====================================================
    # Remove repeated short headings/navigation labels
    # case-insensitively
    # =====================================================

    cleaned_lines = _remove_repeated_short_lines(
        cleaned_lines
    )

    # =====================================================
    # Final result
    # =====================================================

    result = "\n".join(
        cleaned_lines
    ).strip()

    if not result:
        raise ValueError(
            "Cleaning produced no usable text"
        )

    return result