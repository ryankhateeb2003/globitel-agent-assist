# Ingestion Issues & Rejection Documentation

This document records every difficult case and problem encountered while building the ingestion pipeline for HTML, DOCX, and PDF formats, how each was handled, and which inputs are rejected with a clear error.

---

## Summary of Encountered Issues & Handling

| Input / Issue Type | Description | Handling / Pipeline Action | Status / Result |
| :--- | :--- | :--- | :--- |
| **Empty File (0 Bytes)** | File exists on disk but has 0 bytes (e.g. `corpus/en/empty_page.html`). | Pipeline checks `st_size == 0` and raises `ValueError("Document is empty: <path>")`. | **Rejected Cleanly** |
| **Scanned PDF (No Text Layer)** | PDF containing only scanned images with no selectable text (`corpus/ar/scanned_no_text.pdf`). | `extract_pdf` finds zero usable text blocks and raises `ValueError("PDF contains no usable text layer...")`. | **Rejected Cleanly** |
| **Boilerplate-only Extraction** | Document where navigation/header/footer filtering strips all text, leaving nothing. | Pipeline checks if final text is empty and raises `ValueError("Pipeline produced no usable text")`. | **Rejected Cleanly** |
| **Reversed/Reordered Arabic Text in PDF (Bidi Failure)** | `corpus/ar/mobile-lines.pdf`, produced by weasyprint, has Arabic glyphs corrupted at the character level ("شخيص" instead of "شخصي", "إنرتنت" instead of "إنترنت"). Confirmed as a defect in the PDF itself (not extraction order) since per-word extraction is already garbled. English PDF from the same generator is unaffected. | `_check_bidi_against_html` compares the PDF's extracted text against its matching HTML twin using `difflib.SequenceMatcher`. Measured similarity was **0.24**, far below the 0.5 threshold, so the file is rejected rather than repaired (character-level reordering fixes are unreliable and risk silently corrupting content further). | **Rejected Cleanly, with measured evidence** |
| **Navigation & UI Noise (English)** | Headers, footers, breadcrumbs, app menus, language switchers. | Structural selectors in HTML (`<header>`, `<nav>`, CSS classes), exact-match sets in DOCX (`REMOVE_EXACT`, `NAVIGATION_BLOCK`), and block-level filtering in PDF. | **Filtered Out effectively** — e.g. `orange-money.docx` (EN): 33,901 → 27,789 chars (18% removed), result starts directly at real content. |
| **Navigation & UI Noise (Arabic) — Known Limitation** | The same Arabic-language site menu items (e.g. "خطوط الزوار", "خدمات الخلوي", "انترنت الاقمار الصناعية") are **not fully filtered** in DOCX, because `NAVIGATION_BLOCK` was built primarily from the English menu labels; only a few Arabic entries were added. | Not fixed in this pass — documented as a known gap rather than patched, since it affects noise level (extra non-content lines before the real Q&A), not correctness (no real content is lost or corrupted, unlike the bidi case). | **Known limitation** — e.g. `orange-money.docx` (AR): 31,170 → 27,510 chars (only 12% removed vs. 18% for EN); Arabic Q&A content is present later in the extraction and is not affected. Recommended fix: extend `NAVIGATION_BLOCK` with the Arabic-language equivalents, or reuse the frequency-based cross-page boilerplate detection already used for HTML. |
| **Manual Language Mislabeling During Corpus Collection** | orange.jo's `/ar/...` URLs initially returned English-language content when saved without first switching the site's language toggle in the browser — the saved `ar_*.html` files were byte-for-byte near-identical to their `en_*` counterparts (both ~67 Arabic characters, all boilerplate). | Caught via an Arabic-character-ratio check (Unicode range U+0600–U+06FF) comparing each `ar_*` file against expectation before adding it to the corpus. Files were re-collected by explicitly toggling the site to Arabic before saving, then re-verified (3,265–23,022 Arabic chars per page vs. ~67–86 before). | **Caught and corrected during corpus collection** |
| **Merged PDF Headings** | Headings in PDF text merging into the first sentence of the paragraph below them. | `_split_heading_content` / `_looks_like_continuation` detect short, unpunctuated title-like lines and prevent them from being merged into the following sentence. | **Separated Cleanly** |
| **Mixed Language / UI Strings** | Combined strings like `Englishالعربية`, or UI chrome like `Dark mode`, `A-`/`A`/`A+` (font-size widget). | Regex and exact-set matching (`_is_language_control`, `_is_ui_line`, and a short-line length filter for artifacts like `A-`/`A+` that render differently per format). | **Filtered Out** |

---

## Rejection Validation Tests

All 3 required difficult edge cases are covered:
1. **Empty file** → `ValueError` raised.
2. **Scanned PDF (no text layer)** → `ValueError` raised.
3. **Boilerplate-only extraction** → `ValueError` raised.

Plus one additional case discovered during testing, not originally anticipated but directly relevant to the task's Arabic-quality requirements:

4. **Reversed/reordered Arabic PDF text (bidi failure)** → `ValueError` raised, with a measured similarity score (0.24) against the matching HTML page logged in the error message.

---

## Idempotency

Each processed document is assigned a `doc_id` derived from `sha256(source_file_path + raw_file_bytes)` (see `metadata.py`). Re-running ingestion on an unchanged file produces the same `doc_id`, so downstream storage can detect and skip duplicates rather than re-inserting the same content.