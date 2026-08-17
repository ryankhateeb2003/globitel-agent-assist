"""
Builds the final chunk dataset for embedding: reads every document in the
corpus, extracts + cleans it (Task 1 pipeline), splits it using the
"structure" strategy (Task 2's chosen strategy for both languages), and
writes one JSON object per chunk to chunks.jsonl.

This is the missing link between Task 2 (chunking logic, tested in
isolation) and Task 3 (embedding + storage), which needs a persisted,
metadata-tagged dataset to work from.
"""

import json
from pathlib import Path

from app.ingestion.pipeline import extract_document
from app.ingestion.metadata import _infer_language, _infer_topic, _make_doc_id
from app.chunking.chunker import chunk_text
import tiktoken

_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


CHUNK_STRATEGY = "structure"  # decision from Task 2, applied to both languages


def build_chunk_records(corpus_dir: str | Path = "corpus") -> list[dict]:
    """
    Walk the corpus, extract + clean each document, chunk it, and return
    a flat list of chunk records ready to serialize.
    """
    corpus_path = Path(corpus_dir)
    records = []

    files = sorted(corpus_path.glob("**/*.*"))

    for file_path in files:
        # Skip known bad inputs the same way ingest.py does -- these are
        # supposed to fail extraction, so don't even try to chunk them.
        if file_path.name.startswith(".") or "empty" in file_path.name or "scanned" in file_path.name:
            continue

        try:
            text = extract_document(file_path)
        except Exception as exc:
            print(f"[SKIP] {file_path}: {exc}")
            continue

        language = _infer_language(file_path)
        topic = _infer_topic(file_path)
        doc_id = _make_doc_id(file_path, file_path.read_bytes())

        chunks = chunk_text(text, strategy=CHUNK_STRATEGY, language=language)

        for i, chunk_text_value in enumerate(chunks):
            chunk_text_value = chunk_text_value.strip()
            if not chunk_text_value:
                continue

            records.append(
                {
                    "chunk_id": f"{doc_id}_{i:03d}",
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "text": chunk_text_value,
                    "language": language,
                    "topic": topic,
                    "source_file": str(file_path.as_posix()),
                    "source_format": file_path.suffix.lower().lstrip("."),
                    "strategy": CHUNK_STRATEGY,
                    "char_count": len(chunk_text_value),
                    "token_count": count_tokens(chunk_text_value),
                }
            )

        print(f"[OK] {file_path} -> {len(chunks)} chunks")

    return records


def save_jsonl(records: list[dict], output_path: str | Path = "chunks.jsonl") -> None:
    output_path = Path(output_path)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n[SAVED] {len(records)} chunks -> {output_path}")


if __name__ == "__main__":
    records = build_chunk_records()
    save_jsonl(records)

    en_count = sum(1 for r in records if r["language"] == "en")
    ar_count = sum(1 for r in records if r["language"] == "ar")
    print(f"English chunks: {en_count}")
    print(f"Arabic chunks : {ar_count}")