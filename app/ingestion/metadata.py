import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import extract_document


def _infer_language(file_path: Path) -> str:
    """
    Infer language from the corpus folder structure: corpus/en/... or corpus/ar/...
    """
    parts = {p.lower() for p in file_path.parts}
    if "ar" in parts:
        return "ar"
    if "en" in parts:
        return "en"
    return "unknown"


def _infer_topic(file_path: Path) -> str:
    """
    Infer topic from the filename, e.g. 'mobile-lines.html' -> 'mobile-lines'.
    """
    return file_path.stem


def _make_doc_id(file_path: Path, raw_bytes: bytes) -> str:
    """
    Stable hash from the source path + raw file content.
    Same input file (unchanged) always produces the same doc_id,
    which is what makes re-running ingestion idempotent.
    """
    hasher = hashlib.sha256()
    hasher.update(str(file_path.as_posix()).encode("utf-8"))
    hasher.update(raw_bytes)
    return hasher.hexdigest()[:16]


def build_document(file_path: str | Path) -> dict:
    """
    Wrap extract_document() with the metadata required by Task 1:
    doc_id, language, topic, source_file, source_format, ingestion_date,
    plus a status/reject_reason pair so failures are recorded, not thrown away.
    """
    file_path = Path(file_path)

    raw_bytes = file_path.read_bytes() if file_path.exists() else b""

    doc = {
        "doc_id": _make_doc_id(file_path, raw_bytes),
        "text": "",
        "language": _infer_language(file_path),
        "topic": _infer_topic(file_path),
        "source_file": str(file_path.as_posix()),
        "source_format": file_path.suffix.lower().lstrip("."),
        "section_heading": None,  # current extractors return flat text; see note below
        "ingestion_date": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "reject_reason": None,
    }

    try:
        doc["text"] = extract_document(file_path)
    except Exception as exc:
        doc["status"] = "rejected"
        doc["reject_reason"] = str(exc)

    return doc