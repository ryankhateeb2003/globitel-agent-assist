"""
Small manual-testing tool -- shows the full text of the retrieved chunks
for a question, so you can eyeball whether the question and its answer
live in the SAME chunk or got split across different chunks.

Usage (run inside the container, since retrieval needs Qdrant + the
embedding/reranker models that only exist there):

    docker exec -it globitel-app python show_chunks.py "your question here"

Optional flags:
    --mode vector|keyword|hybrid   (default: hybrid)
    --top_k N                      (default: 5)
    --full                         print the FULL chunk text, not just
                                    a preview (default: preview only)
"""

import argparse

from app.retrieval.retrieval import search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="the question to search for")
    parser.add_argument("--mode", default="hybrid", choices=["vector", "keyword", "hybrid"])
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--full", action="store_true", help="print full chunk text")
    args = parser.parse_args()

    outcome = search(args.question, mode=args.mode, top_k=args.top_k)

    print(f"\nQuestion: {args.question}")
    print(f"Mode: {outcome['mode']} | elapsed: {outcome['elapsed_ms']} ms")
    print(f"Retrieved {len(outcome['results'])} chunk(s)\n" + "=" * 80)

    for i, r in enumerate(outcome["results"], start=1):
        score = r.get("rerank_score", r.get("rrf_score", r.get("score")))
        print(f"\n--- Chunk #{i} ---")
        print(f"chunk_id     : {r.get('chunk_id')}")
        print(f"source_file  : {r.get('source_file')}")
        print(f"score        : {score}")
        text = r.get("text", "")
        print(f"text ({len(text)} chars):")
        print(text if args.full else (text[:400] + ("..." if len(text) > 400 else "")))
        print("-" * 80)


if __name__ == "__main__":
    main()

