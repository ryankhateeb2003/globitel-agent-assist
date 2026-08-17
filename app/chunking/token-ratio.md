# Token Ratio Analysis

## Objective

Arabic and English do not produce the same number of tokens for the same number of characters.

Because the chunking strategy is ultimately processed by an LLM tokenizer, this difference affects:

* the effective token size of each chunk,
* the amount of context sent to the model,
* retrieval context size,
* and potentially the cost per query.

The token ratio was therefore measured separately for English and Arabic using the tokenizer of the target model.

---

## Tokenizer Used

The tokenizer used for this measurement is:

`Qwen/Qwen2.5-3B-Instruct`

The tokenizer was loaded using Hugging Face Transformers.

PyTorch was not required for this test because only the tokenizer was used. The test measures tokenization and does not load or run the model itself.

---

## Terminal Test

The following command was used to measure the number of characters, number of tokens, and tokens per 100 characters for the English and Arabic Orange Money documents.

### Terminal command

```powershell id="w8qj7k"
python -c "from app.ingestion.pipeline import extract_document; from transformers import AutoTokenizer; files=[('en','corpus/en/orange-money.docx'),('ar','corpus/ar/orange-money.docx')]; tok=AutoTokenizer.from_pretrained('Qwen/Qwen2.5-3B-Instruct'); [(lambda t: print(f'{lang.upper()} | chars={len(t)} | tokens={len(tok.encode(t,add_special_tokens=False))} | tokens_per_100_chars={len(tok.encode(t,add_special_tokens=False))/len(t)*100:.2f}'))(extract_document(path)) for lang,path in files]"
```

---

## Raw Results

### English

```text id="x2h8m3"
EN | chars=27789 | tokens=5841 | tokens_per_100_chars=21.02
```

### Arabic

```text id="p6y1kf"
AR | chars=27510 | tokens=10637 | tokens_per_100_chars=38.67
```

---

## Summary

| Language | Characters | Tokens | Tokens per 100 Characters |
| -------- | ---------: | -----: | ------------------------: |
| English  |     27,789 |  5,841 |                 **21.02** |
| Arabic   |     27,510 | 10,637 |                 **38.67** |

The two documents contain almost the same amount of text by character count, making them useful for comparing tokenization efficiency between the two languages.

---

## Arabic Token Overhead

The Arabic token ratio is:

**38.67 tokens per 100 characters**

The English token ratio is:

**21.02 tokens per 100 characters**

The relative Arabic token overhead compared with English is:

[
\frac{38.67-21.02}{21.02}\times100 \approx 83.97%
]

Therefore:

**Arabic has approximately 84% higher token overhead than English for this corpus and tokenizer.**

Another way to express the same result is:

[
\frac{38.67}{21.02}\approx1.84
]

Arabic text produced approximately **1.84× as many tokens per character** as English text in this measurement.

---

## What This Means for Chunk Size

A character-based chunk size does not represent the same number of tokens in Arabic and English.

For example, using the measured ratios:

### 1,000 characters

English:

[
1000\times\frac{21.02}{100}\approx210\ tokens
]

Arabic:

[
1000\times\frac{38.67}{100}\approx387\ tokens
]

Therefore, a 1,000-character chunk is approximately:

* **210 tokens in English**
* **387 tokens in Arabic**

The same character limit therefore creates a much larger token context for Arabic.

---

## Effect on the Chunking Strategies

The measured token ratio helps explain the earlier chunk statistics.

### Fixed-size

The fixed strategy uses approximately the same character budget for both languages.

The measured averages were:

| Language | Avg Characters | Avg Tokens |
| -------- | -------------: | ---------: |
| English  |          988.3 |      208.1 |
| Arabic   |          980.3 |      377.5 |

Although both languages have almost the same average character count, the Arabic chunks contain substantially more tokens.

This demonstrates why character-based limits cannot be interpreted as equivalent token limits across languages.

---

### Sentence-based

The sentence strategy produced:

| Language | Avg Characters | Avg Tokens |
| -------- | -------------: | ---------: |
| English  |          841.1 |      176.9 |
| Arabic   |          886.5 |      339.9 |

Again, Arabic uses substantially more tokens for a similar amount of text.

---

### Structure-based

The structure strategy produced:

| Language | Avg Characters | Avg Tokens |
| -------- | -------------: | ---------: |
| English  |          247.1 |       51.6 |
| Arabic   |          244.6 |       94.5 |

This strategy naturally creates smaller chunks because each FAQ question-answer pair is treated as a retrieval unit.

Even though Arabic still requires more tokens, the resulting chunks remain relatively small in token terms.

---

## Token Ratio and LLM Cost

LLM APIs generally charge according to the number of tokens processed rather than the number of characters.

Therefore, if the same amount of information is represented in Arabic and English, the Arabic version can require more input tokens.

For this corpus:

* English: approximately **21.02 tokens per 100 characters**
* Arabic: approximately **38.67 tokens per 100 characters**
* Arabic overhead: approximately **84%**

This does not mean that every Arabic request will cost exactly 84% more than its English equivalent. Actual cost depends on the exact text, tokenizer behavior, prompt, retrieved chunks, output tokens, and model pricing.

However, the measurement demonstrates that Arabic tokenization is significantly less compact for this corpus.

---

## Important Interpretation

The 84% figure is a measured property of this corpus using the Qwen2.5-3B-Instruct tokenizer.

It should not be treated as a universal property of Arabic.

Tokenization efficiency can vary depending on:

* tokenizer,
* model,
* Arabic spelling and normalization,
* punctuation,
* numbers,
* English words inside Arabic text,
* URLs,
* special characters,
* and document formatting.

Therefore, the correct conclusion for this project is:

> With the Qwen2.5-3B-Instruct tokenizer and the tested Orange Money corpus, Arabic produced approximately 84% more tokens per 100 characters than English.

---

## Relation to the Chunking Decision

The token-ratio measurement supports using token-aware reasoning when selecting chunk sizes.

A fixed character limit should not be assumed to represent the same model context in Arabic and English.

For this project, the structure-based strategy was selected for both languages because:

* English achieved 0% broken answers and 100% answer survival.
* Arabic achieved 0% broken answers and 100% answer survival.
* The FAQ structure naturally defines a question-answer retrieval unit.
* Structure-based chunks were substantially smaller than the fixed and sentence-based chunks.
* The smaller chunks reduce unnecessary context passed to the LLM while preserving complete FAQ answers.

The Arabic token overhead is therefore an important consideration when estimating future retrieval context and model usage.

---

## Chunk Token Comparison

The final measured chunk statistics were:

| Language | Strategy  | Avg Characters | Avg Tokens |
| -------- | --------- | -------------: | ---------: |
| English  | Fixed     |          988.3 |      208.1 |
| English  | Sentence  |          841.1 |      176.9 |
| English  | Structure |          247.1 |       51.6 |
| Arabic   | Fixed     |          980.3 |      377.5 |
| Arabic   | Sentence  |          886.5 |      339.9 |
| Arabic   | Structure |          244.6 |       94.5 |

This confirms that Arabic consistently requires more tokens than English for comparable character lengths.

---

## Conclusion

The tokenization test confirms a significant difference between English and Arabic.

The measured ratios were:

**English: 21.02 tokens / 100 characters**

**Arabic: 38.67 tokens / 100 characters**

Therefore, Arabic had an approximately:

**84% token overhead**

relative to English in the tested corpus using the Qwen2.5-3B-Instruct tokenizer.

This difference must be considered when designing chunk sizes and estimating future LLM context usage and query costs.
