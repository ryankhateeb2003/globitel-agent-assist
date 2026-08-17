# API Tests — POST /ask

4 required test cases for the /ask endpoint, run against the live server
(not internal function calls).

---

## Test 1: Normal question

**Request:**
```json
{"question": "What is QR Payment?"}
```

**Result:** `200 OK`

**Answer:** "QR Payment is a secure digital payment method provided by Orange Money that allows you to scan barcodes using your smartphone camera."

**Sources:** `corpus/en/orange-money.docx`, `corpus/en/orange-money.html`

**Token usage:** 459 prompt + 25 completion = 484 total

**Verdict:** Pass. Grounded, concise answer with correct sources.

---

## Test 2: Empty question

**Request:**
```json
{"question": ""}
```

**Result:** `400 Bad Request`

**Response:**
```json
{"error": "Question cannot be empty."}
```

**Verdict:** Pass. Rejected before retrieval or any Groq call was made -- no tokens spent on an invalid request, clear error returned instead of an empty or crashed response.

---

## Test 3: Very long question

**Request:** the string `"What is QR Payment? "` repeated 60 times (1199 characters).

**Result:** `400 Bad Request`

**Response:**
```json
{"error": "Question too long (1199 chars). Maximum is 1000."}
```

**Verdict:** Pass. Rejected before retrieval or any Groq call was made, with the actual length and the limit both stated in the error -- same efficiency reasoning as Test 2.

---

## Test 4: Mixed-language question

**Request:**
```json
{"question": "شو رسوم استخدام QR Payment؟"}
```
(Arabic sentence containing an English product/service name, "QR Payment".)

**Result:** `200 OK`

**Detected language:** `ar`

**Answer:** "خدمة الدفع عبر QR مجانية تماماً ولا تدفع أي رسوم."

**Sources:** `corpus/ar/orange-money.docx`, `corpus/ar/orange-money.html`, `corpus/en/orange-money.docx`, `corpus/en/orange-money.html`

**Token usage:** 415 prompt + 13 completion = 428 total

**Verdict:** Pass. The Arabic-character-ratio threshold correctly classified the mixed-script input as Arabic despite the embedded English term, and the answer was generated in Arabic as expected. Retrieval also pulled in the matching English-language chunks (cross-language behavior, consistent with the Task 3 decision not to filter by language) without that affecting the answer's language.

---

## Summary

| Test | Status | Result |
|---|---|---|
| Normal question | 200 | Pass |
| Empty question | 400 | Pass — rejected with clear error, no wasted API call |
| Very long question | 400 | Pass — rejected with clear error, no wasted API call |
| Mixed-language question | 200 | Pass — correct language detection and answer language |
---------------------------------------------------------------



  الملف	الحالة
/ask endpoint (question, language hint, top_k)	✅
كشف لغة تلقائي	✅
جواب بلغة السؤال + مصادر + chunks خام + توكنز	✅
Streaming	✅
prompts/rag_answer_en.txt + rag_answer_ar.txt	✅
ask-examples.md (20 سؤال حقيقي عبر API فعلي)	✅
language-detection.md (30 حالة، 100% دقة)	✅
api-tests.md (4 اختبارات)