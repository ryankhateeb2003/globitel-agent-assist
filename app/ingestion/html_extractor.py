from pathlib import Path

from bs4 import BeautifulSoup


# ---------------------------------------------------------
# HTML elements that never contain documentation content
# ---------------------------------------------------------

REMOVE_TAGS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
]


# ---------------------------------------------------------
# Website/UI structures that should not enter the RAG corpus
# These rules are structural and therefore language-independent.
# ---------------------------------------------------------

REMOVE_SELECTORS = [
    # Global website structure
    "header",
    "footer",
    "nav",

    # Navigation menus that can appear inside <main>
    ".ultimenu",
    ".menu-level-0",
    ".menu-level-1",
    "a.nav-link",

    # Breadcrumbs
    ".breadcrumbs",
    ".breadcrumb",

    # Forms / interactive UI
    "form",
    "button",
    "input",
    "select",
    "textarea",

    # Search / filter UI
    ".views-exposed-form",
    ".view-filters",

    # Orange FAQ / useful-links navigation
    ".help-useful-faqs",
    ".help-useful-links",
    ".block-views-blockhelp-useful-links-help-useful-links",

    # Help / CTA sections
    ".help-wrapper-content",

    # Known CTA content blocks
    ".block-block-contentc0bf4984-705e-4640-9377-18c7ca3fae29",
    ".block-block-contentea3ec12f-c9e9-44dd-8428-f3f8aa9da732",
    ".block-block-contentc1f94acd-4fb4-42ec-9159-fe85aadd43e5",

    # Feedback confirmation
    ".thank-you-message",

    # Help-center category cards / navigation
    ".taxonomy-term--type-faqs-main-categories",

    # Footer components
    ".footer-social-wrapper",
    ".payment-newsletter-wrapper",
    ".footer-copyright-wrapper",
]


def clean_eck_entities(main) -> None:
    """
    Drupal ECK content can appear twice on some pages.

    Navigation/tab ECK entities do not contain a field-body.
    Actual documentation entities do contain field-body.

    Therefore:
        no field-body -> navigation/UI -> remove
        field-body    -> actual content -> keep
    """

    for entity in main.select(".eck-entity"):
        body = entity.select_one(
            ".field--name-field-body"
        )

        if body is None:
            entity.decompose()


def remove_duplicate_lines(lines: list[str]) -> list[str]:
    """
    Remove exact duplicate lines while preserving order.
    """

    seen = set()
    result = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result


def extract_html(file_path: str | Path) -> str:
    """
    Extract clean documentation content from an HTML file.

    Processing pipeline:

    1. Validate input.
    2. Parse HTML.
    3. Remove technical/non-content elements.
    4. Restrict extraction to <main>.
    5. Remove website UI/navigation/CTA structures.
    6. Remove navigation-only ECK entities.
    7. Extract logical text.
    8. Normalize whitespace.
    9. Remove exact duplicate lines.
    10. Return clean documentation text.
    """

    file_path = Path(file_path)

    # -----------------------------------------------------
    # 1. Validate file
    # -----------------------------------------------------

    if not file_path.exists():
        raise FileNotFoundError(
            f"HTML file not found: {file_path}"
        )

    if file_path.stat().st_size == 0:
        raise ValueError(
            f"HTML file is empty: {file_path}"
        )

    html = file_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if not html.strip():
        raise ValueError(
            f"HTML file contains no text: {file_path}"
        )

    # -----------------------------------------------------
    # 2. Parse HTML
    # -----------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # -----------------------------------------------------
    # 3. Remove technical HTML elements
    # -----------------------------------------------------

    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    # -----------------------------------------------------
    # 4. Find main content boundary
    # -----------------------------------------------------

    main = soup.find("main")

    if main is None:
        raise ValueError(
            f"No <main> content found in HTML file: {file_path}"
        )

    # -----------------------------------------------------
    # 5. Remove website/UI/boilerplate structures
    # -----------------------------------------------------

    for selector in REMOVE_SELECTORS:
        for element in main.select(selector):
            element.decompose()

    # -----------------------------------------------------
    # 6. Remove navigation-only ECK entities
    # -----------------------------------------------------

    clean_eck_entities(main)

    # -----------------------------------------------------
    # 7. Extract text
    # -----------------------------------------------------

    text = main.get_text(
        "\n",
        strip=True,
    )

    # -----------------------------------------------------
    # 8. Normalize lines
    # -----------------------------------------------------

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # -----------------------------------------------------
    # 9. Remove exact duplicate lines
    # -----------------------------------------------------

    lines = remove_duplicate_lines(lines)

    # -----------------------------------------------------
    # 10. Build final text
    # -----------------------------------------------------

    clean_text = "\n".join(lines)

    if not clean_text:
        raise ValueError(
            f"HTML extraction produced no usable content: {file_path}"
        )

    return clean_text