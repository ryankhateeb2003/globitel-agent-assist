"""
Task 4, E1 (chunk size) -- preparation step.

Re-chunks the same corpus with the fixed-size strategy at 3 sizes, writes
each set to eval/task4_experiments/chunks/e1_<size>.jsonl, and indexes it
with the production embedding model (globitelai-bge) into its own Qdrant
collection, chunks_e1_<size>. Production's chunks.jsonl and its
collections are never touched -- run_experiment.py points a run at one of
these sets with --chunks e1_<size>.

Text extraction is the same as production (app/chunking/build_dataset.py);
only the splitting step changes. Overlap is ~15% of the chunk size so an
answer cut at a boundary still appears whole in the next chunk.

Usage (inside the app container):
    docker exec -w /app globitel-app python -m eval.task4_experiments.build_chunks
    docker exec -w /app globitel-app python -m eval.task4_experiments.build_chunks --sizes small
"""

import argparse
import json
import uuid
from pathlib import Path

from qdrant_client.models import Distance, VectorParams, PointStruct

from app.ingestion.pipeline import extract_document
from app.ingestion.metadata import _infer_language, _infer_topic, _make_doc_id
from app.chunking.chunker import fixed_size_chunk
from app.chunking.build_dataset import count_tokens
from app.embeddings.embed_store import client
from app.embeddings.globitel_bge import embed_texts, get_api_key

CHUNKS_DIR = Path("eval/task4_experiments/chunks")

# Production (structure) chunks average ~250 chars (AR) / ~275 chars (EN),
# so "small" is roughly production-sized, "large" holds several FAQ entries.
SIZES = {
    "small": {"chunk_size": 300, "overlap": 50},
    "medium": {"chunk_size": 700, "overlap": 100},
    "large": {"chunk_size": 1500, "overlap": 200},
}
VECTOR_DIM = 1024  # globitelai-bge


def collection_for(size: str) -> str:
    return f"chunks_e1_{size}"


def build_records(size: str, corpus_dir: str = "corpus") -> list[dict]:
    params = SIZES[size]
    records = []
    for file_path in sorted(Path(corpus_dir).glob("**/*.*")):
        # Same skip rule as production: these files are meant to fail extraction.
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

        pieces = [p.strip() for p in fixed_size_chunk(text, **params)]
        for i, piece in enumerate(p for p in pieces if p):
            records.append({
                "chunk_id": f"{doc_id}_e1{size[0]}_{i:03d}",
                "doc_id": doc_id,
                "chunk_index": i,
                "text": piece,
                "language": language,
                "topic": topic,
                "source_file": file_path.as_posix(),
                "source_format": file_path.suffix.lower().lstrip("."),
                "strategy": f"fixed_{params['chunk_size']}",
                "char_count": len(piece),
                "token_count": count_tokens(piece),
            })
    return records


def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def index_records(records: list[dict], collection: str) -> None:
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    vectors = embed_texts([r["text"] for r in records], get_api_key())
    points = [
        PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, r["chunk_id"])), vector=v.tolist(), payload=r)
        for r, v in zip(records, vectors)
    ]
    for start in range(0, len(points), 256):
        client.upsert(collection_name=collection, points=points[start:start + 256])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", choices=list(SIZES), default=list(SIZES))
    args = parser.parse_args()

    for size in args.sizes:
        records = build_records(size)
        path = CHUNKS_DIR / f"e1_{size}.jsonl"
        save_jsonl(records, path)
        by_lang = {lang: sum(r["language"] == lang for r in records) for lang in ("en", "ar")}
        print(f"[{size}] {len(records)} chunks {by_lang} -> {path}")

        index_records(records, collection_for(size))
        print(f"[{size}] indexed into Qdrant collection '{collection_for(size)}'")


if __name__ == "__main__":
    main()
