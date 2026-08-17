from pathlib import Path

from .html_extractor import extract_html
from .docx_extractor import extract_docx
from .pdf_extractor import extract_pdf
from .cleaner import clean_text
from .arabic_normalizer import normalize_arabic


def extract_document(file_path: str | Path) -> str:
    """
    Run the complete ingestion pipeline for one document.

    Pipeline:
        File
        -> Extractor
        -> Cleaner
        -> Arabic Normalizer (Arabic only)
        -> Final text
    """

    file_path = Path(file_path)

    # ---------------------------------------------------------
    # 1. Validate file
    # ---------------------------------------------------------

    if not file_path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if file_path.stat().st_size == 0:
        raise ValueError(
            f"Document is empty: {file_path}"
        )

    suffix = file_path.suffix.lower()

    # ---------------------------------------------------------
    # 2. Extract text
    # ---------------------------------------------------------

    if suffix in {".html", ".htm"}:
        text = extract_html(file_path)

    elif suffix == ".docx":
        text = extract_docx(file_path)

    elif suffix == ".pdf":
        text = extract_pdf(file_path)

    else:
        raise ValueError(
            f"Unsupported document format: {suffix}. "
            f"Supported formats: .html, .htm, .docx, .pdf"
        )

    # ---------------------------------------------------------
    # 3. Generic cleaning
    # ---------------------------------------------------------

    text = clean_text(text)

    # ---------------------------------------------------------
    # 4. Arabic normalization
    # ---------------------------------------------------------

    arabic_chars = sum(
        "\u0600" <= char <= "\u06FF"
        for char in text
    )

    if arabic_chars > 0:
        text = normalize_arabic(text)

    # ---------------------------------------------------------
    # 5. Final validation
    # ---------------------------------------------------------

    if not text.strip():
        raise ValueError(
            f"Pipeline produced no usable text: {file_path}"
        )

    return text