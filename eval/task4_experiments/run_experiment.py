"""
Task 4 -- runs ONE configuration of the /ask pipeline over the full
evaluation set (eval/task1_dataset/dataset_v1.json) and writes the
results, split by language, to eval/task4_experiments/results/<name>.json.

It reuses the production pipeline functions (normalize -> hybrid search
-> guardrail -> streamed generation, same models and prompts as
app/api/), but lets one variable be swapped per run without touching the
running server or app/api/config.py:

    --chunks      baseline | e1_small | e1_medium | e1_large   (E1)
    --top_k       chunks fetched and sent to the answer model    (E2)
    --embedding   globitelai_bge | bge_m3                        (E3)
    --prompt_dir  folder holding rag_answer_en.txt / _ar.txt     (E4)

Per item it records:
  - hit@5 / recall@5 / MRR: whether the retrieved text covers the gold
    chunk's text (token coverage >= 80%, see covered()). Text-based rather
    than chunk_id-based, so runs with different chunking stay comparable.
  - faithfulness: the Task 3 judge (gpt-oss-20b, same prompt file).
  - latency per stage, and Qwen tokens for the cost per query.

Progress is saved after every item; re-running the same --name resumes.

Usage (inside the app container):
    docker exec -w /app globitel-app python -m eval.task4_experiments.run_experiment --name baseline
    docker exec -w /app globitel-app python -m eval.task4_experiments.run_experiment --name e1_small --chunks e1_small
    ... --limit 4   (quick smoke test on the first 4 items)
"""

import argparse
import json
import os
import re
import statistics
import time
from pathlib import Path

from groq import Groq

from app.api.config import GROQ_MODEL, GENERATION_TEMPERATURE, GENERATION_MAX_TOKENS, PROMPT_PATHS
from app.chunking.build_dataset import count_tokens
from app.embeddings.embed_store import client as qdrant
from app.guardrails.guardrails import (
    is_arabizi, translate_arabizi_bilingual, normalize_query_for_retrieval,
    merge_chunk_lists, decide_action,
)
from app.rag.language_detect import detect_language
from app.rag.retrieval import _embed_query, _active_collection_name, build_context
from app.retrieval import keyword_search as kw
from app.retrieval.hybrid import reciprocal_rank_fusion
from app.retrieval.retrieval import RERANK_CANDIDATES
from eval.task3_answer_quality.answer_quality import run_judge

DATASET_PATH = Path("eval/task1_dataset/dataset_v1.json")
PRODUCTION_CHUNKS = Path("chunks.jsonl")
RESULTS_DIR = Path("eval/task4_experiments/results")

CHUNK_SETS = {
    "baseline": {"path": PRODUCTION_CHUNKS, "collection": None},  # production collection for the embedding
    "e1_small": {"path": Path("eval/task4_experiments/chunks/e1_small.jsonl"), "collection": "chunks_e1_small"},
    "e1_medium": {"path": Path("eval/task4_experiments/chunks/e1_medium.jsonl"), "collection": "chunks_e1_medium"},
    "e1_large": {"path": Path("eval/task4_experiments/chunks/e1_large.jsonl"), "collection": "chunks_e1_large"},
}

HIT_K = 5               # the master table reports hit rate at 5
COVERAGE_THRESHOLD = 0.8
FAITHFUL_THRESHOLD = 0.8  # same hallucination cut-off as answer-quality-report.md
REFUSAL_ACTIONS = ("out_of_domain", "ambiguous", "no_info", "needs_account_data")


# ---------------------------------------------------------------------
# Token accounting: wraps the Groq client so every non-streamed call made
# inside the production guardrail functions reports its token usage.
# ---------------------------------------------------------------------

class UsageTracker:
    def __init__(self, groq_client: Groq):
        self._groq = groq_client
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        # Lets production code call tracker.chat.completions.create(...)
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        resp = self._groq.chat.completions.create(**kwargs)
        self.add(getattr(resp, "usage", None))
        return resp

    def add(self, usage) -> None:
        if usage is None:
            return
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens or 0
        self.completion_tokens += usage.completion_tokens or 0


# ---------------------------------------------------------------------
# Retrieval -- same hybrid recipe as app/retrieval/retrieval.py, but with
# the collection and chunk file chosen by the run's config.
# ---------------------------------------------------------------------

def hybrid(query: str, top_k: int, collection: str, embedding: str, chunks_path: Path) -> dict:
    t0 = time.perf_counter()
    vector = _embed_query(query, embedding)
    points = qdrant.query_points(collection_name=collection, query=vector, limit=RERANK_CANDIDATES).points
    vector_results = [{**p.payload, "score": round(p.score, 4)} for p in points]
    t1 = time.perf_counter()
    keyword_results = kw.keyword_search(query, top_k=RERANK_CANDIDATES, chunks_path=chunks_path)
    t2 = time.perf_counter()
    fused = reciprocal_rank_fusion([vector_results, keyword_results])
    return {
        "fused": fused,  # full fused ranking, used for hit@5 / MRR
        "results": fused[:top_k],
        "vector_top_score": vector_results[0]["score"] if vector_results else None,
        "vector_ms": (t1 - t0) * 1000,
        "keyword_ms": (t2 - t1) * 1000,
    }


# ---------------------------------------------------------------------
# Retrieval scoring
# ---------------------------------------------------------------------

def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", kw.normalize_for_keyword_match(text)))


def covered(gold_text: str, retrieved_texts: list[str]) -> bool:
    """True when the retrieved texts together contain >= 80% of the gold
    chunk's tokens -- so a gold answer split across two small chunks, or
    sitting inside one large chunk, both still count as found."""
    gold = tokens(gold_text)
    if not gold:
        return False
    seen = set().union(*(tokens(t) for t in retrieved_texts)) if retrieved_texts else set()
    return len(gold & seen) / len(gold) >= COVERAGE_THRESHOLD


def retrieval_scores(gold_texts: list[str], ranking: list[dict]) -> dict:
    top = [c["text"] for c in ranking[:HIT_K]]
    found = [covered(g, top) for g in gold_texts]
    first_rank = None  # rank at which the first gold answer becomes covered
    for rank in range(1, len(ranking) + 1):
        if any(covered(g, [c["text"] for c in ranking[:rank]]) for g in gold_texts):
            first_rank = rank
            break
    return {
        "hit_at_5": any(found),
        "recall_at_5": sum(found) / len(found),
        "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
    }


# ---------------------------------------------------------------------
# One item through the pipeline
# ---------------------------------------------------------------------

def generate(groq_client: Groq, tracker: UsageTracker, prompt_dir: Path | None,
             question: str, language: str, chunks: list[dict]) -> tuple[str, float, float]:
    path = (prompt_dir / PROMPT_PATHS[language].name) if prompt_dir else PROMPT_PATHS[language]
    template = path.read_text(encoding="utf-8")
    prompt = template.replace("{context}", build_context(chunks)).replace("{question}", question)

    start = time.perf_counter()
    ttft = None
    text = ""
    stream = groq_client.chat.completions.create(
        model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}],
        temperature=GENERATION_TEMPERATURE, max_tokens=GENERATION_MAX_TOKENS, stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            ttft = ttft or (time.perf_counter() - start) * 1000
            text += delta
        if getattr(chunk, "x_groq", None) and chunk.x_groq.usage:
            tracker.add(chunk.x_groq.usage)
    return text, ttft, (time.perf_counter() - start) * 1000


def run_item(item: dict, cfg: dict, groq_client: Groq, gold_by_id: dict) -> dict:
    tracker = UsageTracker(groq_client)
    timings = {}
    start = time.perf_counter()
    question = item["question"]
    language = detect_language(question)

    t0 = time.perf_counter()
    if is_arabizi(question):
        language = "ar"
        tr = translate_arabizi_bilingual(tracker, GROQ_MODEL, question)
        timings["normalize"] = (time.perf_counter() - t0) * 1000
        outcomes = [hybrid(q, cfg["top_k"], cfg["collection"], cfg["embedding"], cfg["chunks_path"])
                    for q in (tr["arabic"], tr["english"])]
        results = merge_chunk_lists(*(o["results"] for o in outcomes))[:cfg["top_k"]]
        ranking = merge_chunk_lists(*(o["fused"] for o in outcomes))
        arabizi = True
    else:
        query = normalize_query_for_retrieval(tracker, GROQ_MODEL, question, language)
        timings["normalize"] = (time.perf_counter() - t0) * 1000
        outcomes = [hybrid(query, cfg["top_k"], cfg["collection"], cfg["embedding"], cfg["chunks_path"])]
        results = outcomes[0]["results"]
        ranking = outcomes[0]["fused"]
        arabizi = False
    timings["vector"] = sum(o["vector_ms"] for o in outcomes)
    timings["keyword"] = sum(o["keyword_ms"] for o in outcomes)

    scores = [o["vector_top_score"] for o in outcomes if o["vector_top_score"] is not None]
    t0 = time.perf_counter()
    decision = decide_action(
        tracker, GROQ_MODEL, question, language, results,
        is_arabizi_query=arabizi, confidence_score=max(scores) if scores else None,
        embedding_backend=cfg["embedding"],
    )
    timings["guardrail"] = (time.perf_counter() - t0) * 1000

    answer, ttft, generation_ms = None, None, None
    if decision["action"] == "answer_normally":
        answer, ttft, generation_ms = generate(groq_client, tracker, cfg["prompt_dir"], question, language, results)
    timings["ttft"] = ttft
    timings["generation"] = generation_ms
    timings["total"] = (time.perf_counter() - start) * 1000

    record = {
        "id": item["id"], "language": item["language"], "type": item["type"],
        "question": question, "action": decision["action"], "answer": answer,
        "timings_ms": timings,
        "qwen_tokens": {"prompt": tracker.prompt_tokens, "completion": tracker.completion_tokens, "calls": tracker.calls},
        "context_tokens_sent": sum(count_tokens(c["text"]) for c in results) if answer else 0,
        "retrieved": [{"chunk_id": c["chunk_id"], "source_file": c["source_file"]} for c in results],
    }

    if item["type"] == "should_refuse":
        record["correctly_refused"] = decision["action"] in REFUSAL_ACTIONS
        return record

    gold_texts = [gold_by_id[cid] for cid in item["_chunk_id"].split(",") if cid in gold_by_id]
    record.update(retrieval_scores(gold_texts, ranking))
    if answer:
        judged = run_judge(groq_client, "faithfulness", context=build_context(results), question=question, answer=answer)
        record["faithfulness"] = judged["score"]
        record["faithfulness_reason"] = judged["reason"]
    return record


def run_item_retrieval_only(item: dict, cfg: dict, gold_by_id: dict) -> dict:
    """
    Same retrieval step as run_item, but skips normalize/classify_intent/
    generate/judge entirely -- zero Groq calls, zero quota cost. Only
    hit@5/recall@5/MRR come out of this, which is all E1 (chunk size) and
    E3 (embedding model) are actually comparing; faithfulness/hallucination/
    token numbers for those configs still need a real (--name ..., no
    --retrieval_only) run once quota allows it.
    should_refuse items are skipped by main() before this is called --
    judging a refusal needs classify_intent, which this mode has no way
    to run.
    """
    start = time.perf_counter()
    question = item["question"]
    outcome = hybrid(question, cfg["top_k"], cfg["collection"], cfg["embedding"], cfg["chunks_path"])
    results = outcome["results"]
    ranking = outcome["fused"]
    timings = {
        "normalize": None, "vector": outcome["vector_ms"], "keyword": outcome["keyword_ms"],
        "guardrail": None, "ttft": None, "generation": None,
        "total": (time.perf_counter() - start) * 1000,
    }
    record = {
        "id": item["id"], "language": item["language"], "type": item["type"],
        "question": question, "action": None, "answer": None,
        "timings_ms": timings,
        "qwen_tokens": {"prompt": 0, "completion": 0, "calls": 0},
        "context_tokens_sent": 0,
        "retrieved": [{"chunk_id": c["chunk_id"], "source_file": c["source_file"]} for c in results],
    }
    gold_texts = [gold_by_id[cid] for cid in item["_chunk_id"].split(",") if cid in gold_by_id]
    record.update(retrieval_scores(gold_texts, ranking))
    return record


# ---------------------------------------------------------------------
# Summary, split by language
# ---------------------------------------------------------------------

def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def percentile(values, p):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return round(values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))], 1)


def summarize(records: list[dict], price_in: float | None, price_out: float | None) -> dict:
    summary = {}
    for lang in ("en", "ar"):
        rows = [r for r in records if r["language"] == lang]
        answerable = [r for r in rows if r["type"] != "should_refuse"]
        refuse = [r for r in rows if r["type"] == "should_refuse"]
        answered = [r for r in answerable if r.get("answer")]
        faith = [r["faithfulness"] for r in answered if r.get("faithfulness") is not None]
        totals = [r["timings_ms"]["total"] for r in rows]
        tok_in = mean([r["qwen_tokens"]["prompt"] for r in rows])
        tok_out = mean([r["qwen_tokens"]["completion"] for r in rows])
        cost = None
        if price_in is not None and price_out is not None and tok_in is not None:
            cost = round((tok_in * price_in + tok_out * price_out) / 1_000_000, 6)
        summary[lang] = {
            "n_items": len(rows),
            "hit_at_5": mean([float(r["hit_at_5"]) for r in answerable]),
            "recall_at_5": mean([r["recall_at_5"] for r in answerable]),
            "mrr": mean([r["reciprocal_rank"] for r in answerable]),
            "faithfulness": mean(faith),
            "hallucination_rate": round(sum(f < FAITHFUL_THRESHOLD for f in faith) / len(faith), 4) if faith else None,
            "answerable_answered": f"{len(answered)}/{len(answerable)}",
            "should_refuse_correct": f"{sum(r['correctly_refused'] for r in refuse)}/{len(refuse)}",
            "latency_p50_ms": percentile(totals, 50),
            "latency_p95_ms": percentile(totals, 95),
            "stage_mean_ms": {s: mean([r["timings_ms"].get(s) for r in rows])
                              for s in ("normalize", "vector", "keyword", "guardrail", "ttft", "generation")},
            "qwen_prompt_tokens_per_query": tok_in,
            "qwen_completion_tokens_per_query": tok_out,
            "context_tokens_per_answer": mean([r["context_tokens_sent"] for r in answered]),
            "cost_per_query_usd": cost,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="results file name, e.g. baseline or e1_small")
    parser.add_argument("--chunks", choices=list(CHUNK_SETS), default="baseline")
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--embedding", choices=["globitelai_bge", "bge_m3"], default="globitelai_bge")
    parser.add_argument("--prompt_dir", type=Path, default=None, help="folder with rag_answer_en.txt / rag_answer_ar.txt")
    parser.add_argument("--limit", type=int, default=None, help="only the first N items (smoke test)")
    parser.add_argument("--ids", nargs="+", default=None, help="only these dataset item ids")
    parser.add_argument("--price_in", type=float, default=None, help="USD per 1M Qwen input tokens")
    parser.add_argument("--price_out", type=float, default=None, help="USD per 1M Qwen output tokens")
    parser.add_argument("--retrieval_only", action="store_true",
                         help="skip normalize/classify/generate/judge (zero Groq calls) -- "
                              "hit@5/recall@5/MRR only, no faithfulness/tokens/cost")
    args = parser.parse_args()

    chunk_set = CHUNK_SETS[args.chunks]
    if chunk_set["collection"] and args.embedding != "globitelai_bge":
        parser.error("the e1_* chunk sets are only indexed with globitelai_bge")
    cfg = {
        "chunks": args.chunks,
        "chunks_path": chunk_set["path"],
        "collection": chunk_set["collection"] or _active_collection_name(args.embedding),
        "top_k": args.top_k,
        "embedding": args.embedding,
        "prompt_dir": args.prompt_dir,
    }

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if args.ids:
        dataset = [d for d in dataset if d["id"] in args.ids]
    if args.retrieval_only:
        dataset = [d for d in dataset if d["type"] != "should_refuse"]
    dataset = dataset[: args.limit]
    gold_by_id = {}
    with PRODUCTION_CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            gold_by_id[c["chunk_id"]] = c["text"]

    out_path = RESULTS_DIR / f"{args.name}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    if out_path.exists():
        records = json.loads(out_path.read_text(encoding="utf-8"))["items"]
    done = {r["id"] for r in records}

    groq_client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=8)
    config_out = {k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.items()}

    def save(complete: bool) -> None:
        out = {
            "name": args.name, "config": config_out, "complete": complete,
            "generation_model": GROQ_MODEL,
            "summary_by_language": summarize(records, args.price_in, args.price_out),
            "items": records,
        }
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for i, item in enumerate(dataset, 1):
        if item["id"] in done:
            continue
        record = (run_item_retrieval_only(item, cfg, gold_by_id) if args.retrieval_only
                   else run_item(item, cfg, groq_client, gold_by_id))
        records.append(record)
        save(complete=False)
        print(f"[{i}/{len(dataset)}] {item['id']} action={record['action']} "
              f"hit@5={record.get('hit_at_5')} faith={record.get('faithfulness')} "
              f"total={record['timings_ms']['total']:.0f}ms", flush=True)

    save(complete=True)
    print(json.dumps(summarize(records, args.price_in, args.price_out), indent=2))
    print(f"[SAVED] {out_path}")


if __name__ == "__main__":
    main()
