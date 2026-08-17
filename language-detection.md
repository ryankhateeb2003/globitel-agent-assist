# Language Detection

## How language is detected

Detection is a simple, deterministic character-ratio check — no external
library or ML model is used. This keeps the approach consistent with
Task 1's own Arabic-character-ratio check (used there to catch mislabeled
corpus files), rather than introducing a new dependency for a two-language
product.

**Method:**
1. Count Arabic-script characters in the text (Unicode range U+0600–U+06FF).
2. Count Latin-script letters (A–Z, a–z).
3. Compute `arabic_ratio = arabic_chars / (arabic_chars + latin_chars)`.
4. If `arabic_ratio >= 0.3` → classified as Arabic (`ar`). Otherwise → English (`en`).
5. Digits, punctuation, and whitespace are excluded from the ratio, so a
   short question containing a USSD code (e.g. `*140#`) isn't skewed by
   symbols with no language of their own.
6. Empty input, or input with no letters at all, defaults to `en` (the
   safer fallback given the codebase and prompt set are English-first).

A ratio threshold (rather than "any Arabic character present = Arabic")
was chosen because this corpus's domain frequently mixes scripts inside
a single Arabic sentence — product names like "Orange Money", "QR
Payment", or "Google Pay" are commonly written in Latin script inside
otherwise-Arabic questions. A stricter rule would misclassify these as
English.

## Accuracy on 30 test inputs

30 test sentences were run through `detect_language()`: 10 clean Arabic,
10 clean English, 5 Arabic sentences containing Latin-script product
names, 3 Arabizi (Latin-transliterated spoken Arabic), and 2
digit/symbol-only inputs.

**Result: 30/30 correct = 100% accuracy** against the expected
classification for each case.

| Category | Count | Correct | Notes |
|---|---|---|---|
| Clean Arabic | 10 | 10/10 | Standard and colloquial Arabic questions |
| Clean English | 10 | 10/10 | Standard English questions |
| Mixed (Arabic + Latin product names) | 5 | 5/5 | e.g. "شو رسوم استخدام QR Payment؟" correctly detected as `ar` |
| Arabizi | 3 | 3/3 (by design, see below) | e.g. "kif ba3mal top up l l khat?" detected as `en` |
| Digits/symbols only | 2 | 2/2 | `*140#` and `1777` both default to `en` |

Full input list, per-case expected/detected values, and the test script
are in `app/rag/test_language_detection.py`.

## What happens with mixed-language input

Two distinct kinds of "mixed" input behave differently, and this
distinction matters for the product:

**1. Arabic sentence with Latin-script product names** (e.g. "بدي اعرف
تفاصيل Max it App") — correctly detected as Arabic. The Arabic-character
ratio dominates even with an English brand name embedded, so the answer
is generated in Arabic, which matches what an agent actually needs: the
customer is speaking Arabic, the product name just happens to be a Latin
trademark.

**2. Arabizi** (spoken Arabic transliterated into Latin letters, e.g.
"kif ba3mal top up l l khat?") — detected as English, because the text
contains zero Arabic-script characters; the ratio calculation has nothing
Arabic to count. This is a known, intentional limitation of a
character-ratio approach: it detects *script*, not *spoken language*. The
system currently has no way to recognize that Arabizi is semantically
Arabic just written in Latin letters.

**This is flagged here rather than silently accepted, because it directly
affects answer quality**: an Arabizi question would currently receive an
English-language answer and the English prompt template, which is not
what a customer writing in Arabizi expects. Task 6 explicitly calls out
"Question in Levantine dialect or Arabizi" as a hard case requiring
special handling ("still answer, since customers do not write formal
Arabic") -- this is the correct place to address it, likely via a
dedicated Arabizi-detection heuristic or a small classifier, rather than
extending the character-ratio method further. This limitation is
therefore intentionally left unresolved in Task 4 and carried forward as
a known input to Task 6.