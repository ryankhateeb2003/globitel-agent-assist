"""
Embeddings and vector store for the bilingual agent-assist corpus.

Part 1: Qdrant connection + collection setup.
Part 2: Load chunks.jsonl, embed with each model, upsert into Qdrant.

Two separate collections are used, one per embedding model, because each
model produces vectors of a different dimension (384 vs 1024) -- Qdrant
collections require a fixed vector size, so they cannot be mixed.
"""

import hashlib
import json
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer


def stable_point_id(chunk_id: str) -> int:
    """
    Deterministic chunk_id -> Qdrant point ID.

    Python's built-in hash() is salted per-process (PYTHONHASHSEED is not
    pinned anywhere in this project), so the same chunk_id produced a
    different point_id every time this module was imported in a fresh
    process -- re-running embed_and_store() after a restart wouldn't
    overwrite existing points, it would insert duplicates alongside them,
    silently breaking both idempotency and the update path. sha256 is
    stable across processes and machines, so the same chunk_id always maps
    to the same point_id.
    """
    return int(hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()[:12], 16)


# =========================================================
# Connection
# =========================================================

# "qdrant" is the Docker Compose service name, resolvable as a hostname
# only from inside the shared Docker network (i.e. from the app container).
# It is NOT "localhost" here, because we are no longer calling Qdrant from
# the host machine -- both containers now live on the same Docker network.
QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333


# `timeout` (seconds) -- Qdrant's own default client-side timeout is
# short (5s), which is fine for a single vector search but too tight
# once other CPU-heavy work (the reranker's cross-encoder inference, in
# Task 5/6's hybrid path) is competing for the same CPU-only container's
# cores and pushes a query's response time past that window. This isn't
# a Qdrant server change, just how long the client waits before giving
# up -- it never affects query results, only how patient the client is.
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=30)


# =========================================================
# Model registry: name -> (HF model name, vector dimension)
# =========================================================

MODEL_DIMENSIONS = {
    "minilm_en": 384,   # sentence-transformers/all-MiniLM-L6-v2 (English-only baseline)
    "bge_m3": 1024,     # BAAI/bge-m3 (multilingual, the realistic choice)
}

MODEL_HF_NAMES = {
    "minilm_en": "sentence-transformers/all-MiniLM-L6-v2",
    "bge_m3": "BAAI/bge-m3",
}

# Cache loaded models so we don't reload them on every call.
_LOADED_MODELS = {}


def get_model(model_key: str) -> SentenceTransformer:
    if model_key not in _LOADED_MODELS:
        hf_name = MODEL_HF_NAMES[model_key]
        print(f"[LOADING] {hf_name} ...")
        _LOADED_MODELS[model_key] = SentenceTransformer(hf_name)
    return _LOADED_MODELS[model_key]


# =========================================================
# Collection management
# =========================================================

def collection_name(model_key: str) -> str:
    """
    Naming convention: one collection per model, prefixed for clarity.
    e.g. "chunks_minilm_en", "chunks_bge_m3"
    """
    return f"chunks_{model_key}"


def ensure_collection(model_key: str, recreate: bool = False) -> None:
    """
    Create a Qdrant collection for the given model if it doesn't exist yet.

    recreate=True drops and rebuilds it -- useful during development, but
    NOT what we want once real data is loaded (that would defeat the
    "update path" requirement in Task 3, which needs a single changed page
    to be re-indexed without rebuilding everything).
    """
    if model_key not in MODEL_DIMENSIONS:
        raise ValueError(
            f"Unknown model_key '{model_key}'. Choose from: {list(MODEL_DIMENSIONS)}"
        )

    name = collection_name(model_key)
    dim = MODEL_DIMENSIONS[model_key]

    exists = client.collection_exists(name)

    if exists and not recreate:
        print(f"[SKIP] Collection '{name}' already exists.")
        return

    if exists and recreate:
        client.delete_collection(name)
        print(f"[DELETED] Existing collection '{name}' (recreate=True).")

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"[CREATED] Collection '{name}' (dim={dim}, distance=cosine)")


def setup_all_collections(recreate: bool = False) -> None:
    """Create both collections (minilm_en, bge_m3) in one call."""
    for model_key in MODEL_DIMENSIONS:
        ensure_collection(model_key, recreate=recreate)


# =========================================================
# Chunk loading
# =========================================================

def load_chunks(path: str | Path = "chunks.jsonl") -> list[dict]:
    path = Path(path)
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# =========================================================
# Embedding + storage
# =========================================================

def embed_and_store(model_key: str, chunks_path: str | Path = "chunks.jsonl", batch_size: int = 32) -> dict:
    """
    Embed every chunk with the given model and upsert into its Qdrant
    collection. Returns timing/count stats for the comparison report.

    Uses each chunk's existing chunk_id (stable, content-derived) as the
    source for the Qdrant point ID -- this is what makes the "update path"
    possible later: re-embedding a changed chunk with the same chunk_id
    overwrites the old vector instead of duplicating it.
    """
    ensure_collection(model_key)

    model = get_model(model_key)
    records = load_chunks(chunks_path)

    name = collection_name(model_key)
    print(f"\n[EMBEDDING] {len(records)} chunks with '{model_key}' -> collection '{name}'")

    start_time = time.time()
    total_upserted = 0

    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start: batch_start + batch_size]
        texts = [r["text"] for r in batch]

        vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

        points = []
        for record, vector in zip(batch, vectors):
            # Qdrant point IDs must be int or UUID -- we hash the string
            # chunk_id into a stable positive integer.
            point_id = stable_point_id(record["chunk_id"])

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "chunk_id": record["chunk_id"],
                        "doc_id": record["doc_id"],
                        "text": record["text"],
                        "language": record["language"],
                        "topic": record["topic"],
                        "source_file": record["source_file"],
                        "source_format": record["source_format"],
                        "chunk_index": record["chunk_index"],
                    },
                )
            )

        client.upsert(collection_name=name, points=points)
        total_upserted += len(points)
        print(f"  ...{total_upserted}/{len(records)} upserted")

    elapsed = time.time() - start_time

    stats = {
        "model_key": model_key,
        "collection": name,
        "chunks_embedded": total_upserted,
        "elapsed_seconds": round(elapsed, 2),
        "chunks_per_second": round(total_upserted / elapsed, 2) if elapsed > 0 else None,
    }
    print(f"[DONE] {stats}")
    return stats

# =========================================================
# Part 3: Update path -- re-index a single changed file
# =========================================================

from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.ingestion.pipeline import extract_document
from app.ingestion.metadata import _infer_language, _infer_topic, _make_doc_id
from app.chunking.chunker import chunk_text
from pathlib import Path
import tiktoken

_update_encoder = tiktoken.get_encoding("cl100k_base")


def delete_chunks_for_file(model_key: str, source_file: str) -> int:
    """
    Delete every point in the given model's collection whose payload
    source_file matches this file. Returns the count of points that
    existed before deletion (Qdrant's delete API does not return a count
    directly, so we look it up first).
    """
    name = collection_name(model_key)

    existing = client.scroll(
        collection_name=name,
        scroll_filter=Filter(
            must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
        ),
        limit=10000,
    )
    existing_count = len(existing[0])

    if existing_count > 0:
        client.delete(
            collection_name=name,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
            ),
        )

    return existing_count


def update_document(file_path: str, model_keys: list[str] | None = None) -> dict:
    """
    Re-index a single changed document: delete its old chunks (for the
    given models) and re-extract, re-chunk, re-embed, and re-insert fresh
    ones. This is the Task 3 "update path" requirement -- a single changed
    page can be re-indexed without rebuilding the whole corpus.
    """
    if model_keys is None:
        model_keys = list(MODEL_DIMENSIONS)

    path = Path(file_path)
    source_file_str = path.as_posix()

    print(f"\n[UPDATE] {source_file_str}")

    # Step 1: delete old chunks for this file, per model
    deleted_counts = {}
    for model_key in model_keys:
        deleted = delete_chunks_for_file(model_key, source_file_str)
        deleted_counts[model_key] = deleted
        print(f"  [DELETED] {deleted} old chunks from '{collection_name(model_key)}'")

    # Step 2: re-extract + re-chunk the file fresh
    text = extract_document(path)
    language = _infer_language(path)
    topic = _infer_topic(path)
    doc_id = _make_doc_id(path, path.read_bytes())

    chunks = chunk_text(text, strategy="structure", language=language)

    records = []
    for i, chunk_value in enumerate(chunks):
        chunk_value = chunk_value.strip()
        if not chunk_value:
            continue
        records.append(
            {
                "chunk_id": f"{doc_id}_{i:03d}",
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk_value,
                "language": language,
                "topic": topic,
                "source_file": source_file_str,
                "source_format": path.suffix.lower().lstrip("."),
                "strategy": "structure",
                "char_count": len(chunk_value),
                "token_count": len(_update_encoder.encode(chunk_value)),
            }
        )

    print(f"  [RE-CHUNKED] {len(records)} fresh chunks produced")

    # Step 3: re-embed + insert, per model
    inserted_counts = {}
    for model_key in model_keys:
        model = get_model(model_key)
        texts = [r["text"] for r in records]

        if texts:
            vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

            points = []
            for record, vector in zip(records, vectors):
                point_id = stable_point_id(record["chunk_id"])
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector.tolist(),
                        payload=record,
                    )
                )

            client.upsert(collection_name=collection_name(model_key), points=points)

        inserted_counts[model_key] = len(records)
        print(f"  [INSERTED] {len(records)} new chunks into '{collection_name(model_key)}'")

    return {
        "source_file": source_file_str,
        "deleted": deleted_counts,
        "inserted": inserted_counts,
    }
# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":
    setup_all_collections()

    all_stats = []
    for key in MODEL_DIMENSIONS:
        stats = embed_and_store(key)
        all_stats.append(stats)

    print("\n================ SUMMARY ================")
    for s in all_stats:
        print(s)