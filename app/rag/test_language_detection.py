"""
Task 4 deliverable: language-detection.md data.

Runs 30 test inputs through detect_language() covering: clean Arabic,
clean English, mixed Arabic/English (product names in Latin script),
Arabizi (Latin transliteration of spoken Arabic), digits/symbols only,
and short edge-case inputs.
"""

from app.rag.language_detect import detect_language

TEST_CASES = [
    # --- Clean Arabic (10) ---
    ("كيف بقدر افتح محفظة اورنج موني؟", "ar"),
    ("شو هي رسوم استخدام الخدمة؟", "ar"),
    ("متى بيوصل الفني لتركيب الفايبر؟", "ar"),
    ("وين اقرب معرض اورنج؟", "ar"),
    ("ليش ما وصلتني رسالة التأكيد؟", "ar"),
    ("كم رصيدي الحالي؟", "ar"),
    ("هل في رسوم على التحويل الدولي؟", "ar"),
    ("ابغى اعرف تفاصيل باقتي", "ar"),
    ("ما هي خطوات تجديد الاشتراك؟", "ar"),
    ("انا ما قدرت ادخل عالتطبيق", "ar"),

    # --- Clean English (10) ---
    ("How can I open an Orange Money wallet?", "en"),
    ("What are the fees for this service?", "en"),
    ("When will the technician arrive for fiber installation?", "en"),
    ("Where is the nearest Orange shop?", "en"),
    ("Why didn't I receive the confirmation SMS?", "en"),
    ("What is my current balance?", "en"),
    ("Is there a fee for international transfer?", "en"),
    ("I want to know my bundle details", "en"),
    ("What are the renewal steps?", "en"),
    ("I could not log into the app", "en"),

    # --- Mixed Arabic/English -- product names in Latin script (5) ---
    ("كيف بقدر افتح Orange Money wallet؟", "ar"),
    ("شو رسوم استخدام QR Payment؟", "ar"),
    ("بدي اعرف تفاصيل Max it App", "ar"),
    ("هل بقدر اربط Google Pay بمحفظتي؟", "ar"),
    ("وين اقرب Orange shop؟", "ar"),

    # --- Arabizi -- Latin letters, no Arabic script (3) ---
    ("kif ba3mal top up l l khat?", "en"),
    ("wein a2rab shop la orange?", "en"),
    ("shu rusoom l international transfer?", "en"),

    # --- Digits / symbols only, edge cases (2) ---
    ("*140#", "en"),
    ("1777", "en"),
]


def run():
    correct = 0
    total = len(TEST_CASES)

    results = []
    for text, expected in TEST_CASES:
        detected = detect_language(text)
        is_correct = detected == expected
        if is_correct:
            correct += 1
        results.append(
            {"text": text, "expected": expected, "detected": detected, "correct": is_correct}
        )
        status = "OK" if is_correct else "MISMATCH"
        print(f"[{status}] '{text}' -> detected={detected}, expected={expected}")

    accuracy = correct / total * 100
    print(f"\nAccuracy: {correct}/{total} = {accuracy:.1f}%")

    return results, accuracy


if __name__ == "__main__":
    run()