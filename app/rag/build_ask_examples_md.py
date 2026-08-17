"""
Task 4 deliverable: converts ask_examples_raw.json into the final
ask-examples.md report, grouped by language with all 10+10 real
question/answer/source examples documented.
"""

import json


def load_results(path: str = "ask_examples_raw.json") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_entry(i: int, item: dict) -> str:
    if item.get("error"):
        return f"### {i}. {item['question']}\n\n**ERROR:** {item['error']}\n"

    sources_list = "\n".join(f"- `{s}`" for s in item["sources"])
    tokens = item.get("token_usage", {})

    return f"""### {i}. {item['question']}

**Detected language:** {item['detected_language']}

**Answer:**
{item['answer']}

**Sources:**
{sources_list}

**Token usage:** {tokens.get('prompt_tokens', '?')} prompt + {tokens.get('completion_tokens', '?')} completion = {tokens.get('total_tokens', '?')} total

---
"""


def build_report():
    results = load_results()

    en_results = [r for r in results if r["language"] == "en"]
    ar_results = [r for r in results if r["language"] == "ar"]

    lines = [
        "# Ask Examples — /ask Endpoint Real Test Results",
        "",
        "10 English + 10 Arabic questions, sampled from real FAQ content in "
        "chunks.jsonl (random seed=42), sent through the live `/ask` HTTP "
        "endpoint (not an internal function call). Each entry shows the "
        "question, the model's detected language, the streamed answer, the "
        "source documents it was grounded in, and the token cost.",
        "",
        "## English Questions",
        "",
    ]

    for i, item in enumerate(en_results, 1):
        lines.append(format_entry(i, item))

    lines.append("## Arabic Questions")
    lines.append("")

    for i, item in enumerate(ar_results, 1):
        lines.append(format_entry(i, item))

    # Summary stats
    total_tokens = sum(
        r.get("token_usage", {}).get("total_tokens", 0) or 0 for r in results
    )
    errors = sum(1 for r in results if r.get("error"))

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total questions tested: {len(results)} (10 English + 10 Arabic)")
    lines.append(f"- Failed requests: {errors}")
    lines.append(f"- Total tokens consumed across all 20 requests: {total_tokens}")
    lines.append(f"- Average tokens per request: {total_tokens // len(results) if results else 0}")

    report = "\n".join(lines)

    with open("ask-examples.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[SAVED] ask-examples.md ({len(results)} entries, {total_tokens} total tokens)")


if __name__ == "__main__":
    build_report()