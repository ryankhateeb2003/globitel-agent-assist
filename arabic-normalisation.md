# Arabic Normalisation Rules

This document details every Arabic normalisation rule applied in the ingestion pipeline, with before-and-after examples for each rule, and our engineering decision on digit handling with reasons.

---

## Applied Normalisation Rules

### 1. Alef Normalisation (`normalize_alef`)
* **Rule**: Map all forms of Alef (`إ`, `أ`, `آ`, `ٱ`) to plain Alef (`ا`).
* **Reason**: Arabic users and web content alternate between different hamza forms on Alef. Standardising to plain Alef prevents search mismatches when users query without hamza.
* **Before**: `إعادة تعبئة ألكترونية للخطوط المفوترة والمدفوعة مسبقاً`
* **After**: `اعادة تعبئة الكترونية للخطوط المفوترة والمدفوعة مسبقا`

---

### 2. Taa Marbuta Normalisation (`normalize_taa_marbuta`)
* **Rule**: Map Taa Marbuta (`ة`) to Haa (`ه`).
* **Reason**: Spelling variations between `ة` and `ه` are very common in search queries. Normalising to `ه` ensures consistent matching.
* **Before**: `خدمة العملاء متوفرة لجميع المشتركين`
* **After**: `خدمه العملاء متوفره لجميع المشتركين`

---

### 3. Tatweel Removal (`remove_tatweel`)
* **Rule**: Strip all instances of Tatweel/Kashida (`ـ`).
* **Reason**: Tatweel is purely decorative text stretching used in web typography and has no semantic value.
* **Before**: `فـــواتــيــر الــخـطـوط`
* **After**: `فواتير الخطوط`

---

### 4. Diacritics Removal (`remove_diacritics`)
* **Rule**: Remove all short vowel marks (Tashkeel) including Fatha, Damma, Kasra, Sukun, Shadda, and Tanween (`ً ٌ ٍ َ ُ ِ ّ ْ`).
* **Reason**: Arabic text in documentation sometimes carries full diacritics while user queries never include them. Removing diacritics ensures exact character string alignment.
* **Before**: `مُشْتَرَكِي خَطُوطِ أُورَانْج المَحْمُولَةِ`
* **After**: `مشتركي خطوط اورانج المحمولة`

---

### 5. Digit Normalisation (`normalize_arabic_digits`)
* **Rule**: Map all Eastern Arabic-Indic digits (`٠١٢٣٤٥٦٧٨٩`) and Persian digits (`۰۱۲۳۴۵۶۷۸۹`) to Western ASCII digits (`0123456789`).
* **Decision**: **Standardise to Western Digits**.
* **Reasoning**:
  1. Prices (e.g. `5 JOD`), phone numbers (`0777700177`), and short codes (`*140#`) in telecom documentation appear interchangeably using both digit forms.
  2. Embeddings and vector stores handle ASCII digits far more reliably across multi-lingual search queries.
  3. Short code matching and numeric regex patterns perform consistently when all numbers are in standard ASCII.
* **Before**: `سعر الباقة ٥ دنانير وتعمل بالرمز *١٤٠#`
* **After**: `سعر الباقة 5 دنانير وتعمل بالرمز *140#`

---

### 6. Whitespace Normalisation (`normalize_whitespace`)
* **Rule**: Collapse consecutive space/tab characters into a single space and strip leading/trailing whitespace per line.
* **Before**: `  معرفة   الرصيد   والباقات   `
* **After**: `معرفة الرصيد والباقات`
 -------------------------------------------------------
 # Arabic Normalisation Rules

This document lists every Arabic text normalisation rule applied by `arabic_normalizer.py`, 
with a before/after example for each, and the reasoning behind the digit-handling decision.

All rules run only when a document contains Arabic characters (Unicode range U+0600–U+06FF), 
applied as the last step of the pipeline, after boilerplate removal.

---

## 1. Alef variant normalisation

All forms of alef (with hamza above, hamza below, madda, or plain wasla) are collapsed to a 
single plain alef (ا). Arabic text in the wild is inconsistent about which alef variant is 
typed, and a search or embedding index that treats إنترنت and انترنت as different tokens will 
silently miss matches.

| Before | After |
| :--- | :--- |
| الأعمال | الاعمال |
| أورنج | اورنج |
| إنترنت | انترنت |

Source: observed directly in `extraction-samples/orange-money_docx_ar.txt`.

---

## 2. Taa marbuta → haa

Trailing taa marbuta (ة) is converted to haa (ه).

| Before | After |
| :--- | :--- |
| خدمة | خدمه |
| لمساعدة | لمساعده |

Source: observed directly in `extraction-samples/orange-money_docx_ar.txt`.

**Note:** this is a lossy, debatable normalisation — ة and ه are grammatically distinct 
letters, not just stylistic variants, so this trades a small amount of linguistic precision 
for consistent matching. It was chosen because retrieval/search benefit is high here (users 
type both forms inconsistently) and the content is short help-center prose, not literary text 
where the distinction carries more weight.

---

## 3. Tatweel (kashida) removal

The elongation character (ـ, U+0640), sometimes used for visual justification in Arabic text, 
is stripped since it carries no semantic meaning and only adds noise to character/token counts.

**Status: implemented but not encountered in this corpus.** All 14 real corpus pages were 
inspected and no tatweel characters were found in the source HTML. The rule is kept active 
defensively, since scanned or externally-supplied documents commonly introduce it, and 
Task 2 (chunking) and later modules will process documents beyond this initial corpus.

---

## 4. Diacritics (tashkeel) removal

Short vowel marks and other diacritics (fatha, damma, kasra, sukun, shadda, tanween, etc., 
Unicode ranges U+0610–U+061A, U+064B–U+065F, U+0670, U+06D6–U+06ED) are stripped.

| Before | After |
| :--- | :--- |
| مسبقاً | مسبقا |

Source: observed directly in `extraction-samples/orange-money_docx_ar.txt` (tanween case). 
Full vowel diacritics (fatha/damma/kasra) were not found in this corpus — the source pages 
use largely undiacritized Arabic, which is normal for everyday web content. The rule remains 
active defensively for the same reason as tatweel removal above.

---

## 5. Digit normalisation — decision and reasoning

**Decision: convert Arabic-Indic (٠١٢٣...) and Eastern Arabic-Indic (۰۱۲۳...) digits to 
Western digits (0123...) if encountered, applied defensively.**

### What we actually found
All 14 real corpus HTML pages (both languages) were scanned for Arabic-Indic (٠-٩) and 
Eastern Arabic-Indic (۰-۹) digit characters. **Zero occurrences were found.** Every number in 
this corpus — phone numbers (e.g. 1777, 0777700177), short/USSD codes (e.g. *140#), and any 
fees or limits — is already written in Western digits, even on the Arabic-language pages.

### Reasoning
Since the source content (orange.jo) already standardises on Western digits regardless of 
page language, there was no live conflict to resolve in this corpus. The normalisation rule 
is still implemented and kept active in the pipeline, not because it was needed here, but as 
a defensive measure because:
- Live user questions to the `/ask` endpoint (Task 4) may contain Arabic-Indic digits even if 
  the documentation itself doesn't — e.g. an agent typing "١٧٧٧" instead of "1777".
- Future source documents (beyond this initial orange.jo corpus) may not follow the same 
  Western-digit convention.

Converting to Western digits (rather than the reverse) was chosen because Western digits are 
already the corpus's existing standard, so this preserves consistency with 100% of current 
content while guarding against future/query-side variation.

---

## 6. Whitespace normalisation

Repeated spaces/tabs within a line are collapsed to a single space, and lines are trimmed, 
after all the above rules run. This is a general cleanup step (not Arabic-specific) but is 
run in the same pass to avoid a second full-text scan.

---

## Order of operations

Rules run in this fixed order: alef → taa marbuta → tatweel removal → diacritics removal → 
digit conversion → whitespace normalisation. Order matters mainly to keep character-class 
regexes (diacritics, tatweel) working on text that hasn't yet had spacing collapsed, avoiding 
edge cases where a removed diacritic leaves behind a run of spaces that then needs re-collapsing.