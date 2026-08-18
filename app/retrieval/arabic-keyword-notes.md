# Arabic Handling in Keyword Search

## Objective
Vector search compares meaning; keyword search compares tokens. For that
comparison to work at all on Arabic content, the tokens on both sides —
the corpus and the incoming query — have to go through the *same*
normalization. If they don't, keyword search doesn't fail loudly, it
fails silently: it just never finds anything, and looks like "no keyword
matches" instead of "the normalization is broken."

---

## What the analyser does

`keyword_search.py` reuses `normalize_arabic()` from Task 1
(`app/ingestion/arabic_normalizer.py`) — the exact same function applied
to every chunk at ingestion time — and applies it to every incoming query
before tokenizing, on top of `casefold()` for English case-insensitivity.
Nothing Arabic-specific is reimplemented here; the point is that ingestion
and search cannot drift apart because they call the same code.

`normalize_arabic()` applies, in order:

1. **Alef unification** — `إ أ آ ٱ` → `ا`
2. **Taa marbuta → haa** — `ة` → `ه`
3. **Tatweel removal** — `ـ` stripped
4. **Diacritic removal** — tashkeel stripped
5. **Digit normalization** — Arabic-Indic (`٠-٩`) and Eastern Arabic-Indic
   (`۰-۹`) digits → Western digits (`0-9`)
6. **Whitespace normalization**

Tokenizing happens after normalization, with one deliberate exception to
plain word-splitting: USSD short codes (`*979#`) are matched and kept as
a single token (`r"\*\d+(?:\*\d+)*#|[\w؀-ۿ]+"`) instead of being split into
fragments — splitting `*979#` into `979` would lose the exact token this
search exists to catch.

---

## Proof: a normalised query matches normalised content

Ran directly against this project's code (not illustrative pseudocode):

### 1. Taa marbuta
```python
>>> normalize_arabic("خدمة")
'خدمه'
>>> normalize_arabic("خدمه")
'خدمه'
```
Both spellings — the "dictionary" form with taa marbuta and the informal
form with haa, both common in real user input — collapse to the same
string.

### 2. Digits (Arabic-Indic vs. Western) — the case that matters most for this corpus
This corpus is full of short codes and figures that appear in both digit
scripts depending on who typed them. Tokenizing a short code written both
ways:
```python
>>> tokenize("*979#")
['*979#']
>>> tokenize("*٩٧٩#")     # Arabic-Indic digits
['*979#']
```
Same token, both times. And running the two spellings as actual search
queries against the live index returns **identical results, identical
order, identical scores**:

| Query | #1 result | #2 result | #3 result |
|---|---|---|---|
| `*979#` (Western digits) | `49d8a9e384a6bcb9_008` (4.8733) | `49d8a9e384a6bcb9_005` (4.1513) | `16af3a779c48f7a1_002` (3.9703) |
| `*٩٧٩#` (Arabic-Indic digits) | `49d8a9e384a6bcb9_008` (4.8733) | `49d8a9e384a6bcb9_005` (4.1513) | `16af3a779c48f7a1_002` (3.9703) |

Without digit normalization, an agent typing the code in Arabic-Indic
digits (which many Arabic keyboards default to) would get zero keyword
matches on a chunk that plainly contains that exact code — the silent
failure mode this check exists to rule out.

---

## Scoring: BM25, not plain token overlap

An earlier version of this module scored by Jaccard overlap (matching
tokens ÷ query token count), which weights a match on a common word like
"هل" or "كيف" the same as a match on a rare, high-signal word like a
proper noun or a short code. BM25 downweights terms that appear in most
chunks (via IDF) and rewards rare exact matches — which is the entire
reason this hybrid layer exists: to catch the specific values vector
search blurs across similar-meaning chunks.

---

## Known limitation: not filtered by language

Keyword search is not restricted to the query's detected language, for
the same reason vector search isn't (see `cross-language.md`, Task 3): the
English and Arabic pages are translations of the same source content, a
shared token like a short code should surface either version, and
language enforcement happens at the `/ask` answer stage (Task 4), not at
retrieval. In practice this rarely produces literal cross-language
keyword collisions anyway, since Arabic and English word tokens don't
share strings — only shared numerals/codes do, which is the desirable
case above.
