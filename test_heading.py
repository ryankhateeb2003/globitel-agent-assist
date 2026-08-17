"""
TASK 2 FIX (surfaced during Task 5 keyword search testing)
File: test_heading.py (temporary test script -- not part of final pipeline)
Purpose: Iterate on a heading-detection rule for structure_based_chunk
until it correctly separates FAQ headings without splitting numbered
steps, yes/no answers, or navigation menu labels.
"""

from app.ingestion.pipeline import extract_document


def is_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in text)


def is_short_heading(line, next_line, prev_line):
    line = line.strip()
    if len(line) < 3 or len(line) > 50:
        return False
    if line.endswith(('.', '?', '؟', ':', ',', '،')):
        return False
    if next_line is None:
        return False
    if prev_line is not None and len(prev_line) <= 50 and not prev_line.endswith(('.', '?', '؟')):
        return False
    imperative_words = {
        'اضغط', 'ادخل', 'اختر', 'قم', 'انشئ', 'حمل', 'سجل', 'افتح', 'ثم',
        'press', 'click', 'select', 'enter', 'open', 'download', 'create',
        'tap', 'then', 'choose', 'go', 'visit', 'fill', 'add', 'confirm'
    }
    words = line.lower().split()
    if any(w.strip('().,') in imperative_words for w in words[:3]):
        return False
    if line.strip('،, ') in ('نعم', 'لا', 'Yes', 'No', 'yes', 'no'):
        return False
    if ',' in line or '،' in line:
        return False
    connector_prefixes_ar = ('ل', 'و', 'ف', 'ب', 'ك')
    connector_words_en = {'to', 'for', 'this', 'that', 'these', 'those', 'and', 'or', 'with', 'the'}
    first_word = words[0] if words else ''
    if is_arabic(line) and first_word[:1] in connector_prefixes_ar and len(first_word) <= 8:
        return False
    if not is_arabic(line) and first_word in connector_words_en:
        return False
    next_line_stripped = next_line.strip()
    is_real_sentence_after = (
        len(next_line_stripped) >= len(line) * 1.8
        and next_line_stripped.endswith(('.', '?', '؟', ')'))
    )
    if not is_real_sentence_after:
        return False
    if len(words) >= 5:
        return False
    return True


def run_test():
    test_files = [
        'corpus/ar/orange-money.docx',
        'corpus/en/orange-money.docx',
        'corpus/en/mobile-lines.html',
        'corpus/ar/mobile-lines.html',
    ]

    for f in test_files:
        print(f'=== {f} ===')
        text = extract_document(f)
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        count = 0
        for i, line in enumerate(lines):
            prev_line = lines[i - 1] if i > 0 else None
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            if is_short_heading(line, next_line, prev_line):
                count += 1
                print(f'  HEADING: {line[:50]!r}')
        print(f'  Total headings detected: {count}\n')


if __name__ == "__main__":
    run_test()