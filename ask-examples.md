# Ask Examples — /ask Endpoint Real Test Results

10 English + 10 Arabic questions, sampled from real FAQ content in chunks.jsonl (random seed=42), sent through the live `/ask` HTTP endpoint (not an internal function call). Each entry shows the question, the model's detected language, the streamed answer, the source documents it was grounded in, and the token cost.

## English Questions

### 1. How can I use internet while roaming?

**Detected language:** en

**Answer:**
Turn on data roaming on your mobile and make sure that the access point name (APN) is set to net.orange.jo.

**Sources:**
- `corpus/ar/international-roaming.html`
- `corpus/en/international-roaming.html`

**Token usage:** 537 prompt + 28 completion = 565 total

---

### 2. What does it mean for me?

**Detected language:** en

**Answer:**
You will get much faster speeds, which are more suitable for sharing Internet access in your household. Unlike standard broadband, your speed is not determined by the distance from the local telephone exchange.

**Sources:**
- `corpus/ar/international-roaming.html`
- `corpus/ar/orange-money.docx`
- `corpus/en/fiber-adsl.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 408 prompt + 38 completion = 446 total

---

### 3. Can I cancel an International Money transfer?

**Detected language:** en

**Answer:**
I don't have this information in the documentation. Please check with a supervisor or the relevant system.

**Sources:**
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 422 prompt + 21 completion = 443 total

---

### 4. What is QR Payment?

**Detected language:** en

**Answer:**
QR Payment is a secure digital payment method provided by Orange Money that allows most smartphone cameras to read barcodes.

**Sources:**
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 459 prompt + 23 completion = 482 total

---

### 5. Can I close my wallet? How?

**Detected language:** en

**Answer:**
Yes, you can close your wallet by visiting any of our Orange shops. Before doing so, you need to cash out the wallet balance and then fill out the termination form.

**Sources:**
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 440 prompt + 36 completion = 476 total

---

### 6. 1) How can I subscribe to Europe and North America Passenger Bundles?

**Detected language:** en

**Answer:**
To subscribe to Europe and North America Passenger Bundles, please dial *965#.

**Sources:**
- `corpus/en/international-roaming.html`

**Token usage:** 724 prompt + 19 completion = 743 total

---

### 7. How can I disable the roaming data bill control feature?

**Detected language:** en

**Answer:**
You can disable the roaming data bill control feature via the Max it application or by dialing *979#.

**Sources:**
- `corpus/ar/international-roaming.html`
- `corpus/en/international-roaming.html`

**Token usage:** 527 prompt + 24 completion = 551 total

---

### 8. Can I still use my physical Orange Money Visa Card after adding it to Google Pay?

**Detected language:** en

**Answer:**
Yes, your physical Orange Money Visa Card will continue to work as usual. Google Pay is just an additional, convenient way to pay.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 578 prompt + 28 completion = 606 total

---

### 9. Are there any setup fees for new installation or migration to Orange Internet & Orange Internet+ offers?

**Detected language:** en

**Answer:**
Yes, there is a setup and migration fee of 10 JD excluding tax for new installations or migrations to Orange Internet and Orange Internet+ offers.

**Sources:**
- `corpus/ar/fiber-adsl.html`
- `corpus/en/fiber-adsl.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 466 prompt + 31 completion = 497 total

---

### 10. Is my personal information safe?

**Detected language:** en

**Answer:**
Yes, your personal and payment data are securely handled as per the related regulations.

**Sources:**
- `corpus/ar/international-roaming.html`
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 459 prompt + 17 completion = 476 total

---

## Arabic Questions

### 1. هل خدمه الدفع باستخدام رمز الاستجابه السريع مجاني؟

**Detected language:** ar

**Answer:**
نعم، خدمة الدفع باستخدام رمز الاستجابة السريع مجانية.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`

**Token usage:** 585 prompt + 13 completion = 598 total

---

### 2. ما هو الجديد في خدمه الاتصال الصوتي الرقمي مع الفايبر؟

**Detected language:** ar

**Answer:**
بمجرد تركيب خط الفايبر، سيتم تفعيل خدمة الاتصال الصوتي الرقمي فوراً من خلال توصيل جهاز الهاتف الأرضي بفايبر بوكس بشكل مباشر، دون الحاجة إلى أي تمديدات أسلاك نحاسية داخلية.

**Sources:**
- `corpus/ar/fiber-adsl.html`
- `corpus/en/fiber-adsl.html`

**Token usage:** 583 prompt + 51 completion = 634 total

---

### 3. ما هي مميزات خدمه Orange فايبر؟

**Detected language:** ar

**Answer:**
تتميز خدمة Orange فايبر بسرعة إنترنت فائقة ثابتة تصل إلى 1000 ميجابت في الثانية، مع سعة تحميل غير محدودة. كما توفر حماية عالية للأمان وتجربة متميزة عند استخدام كافة أنواع التطبيقات.

**Sources:**
- `corpus/ar/fiber-adsl.html`
- `corpus/en/fiber-adsl.html`

**Token usage:** 616 prompt + 53 completion = 669 total

---

### 4. كيف استطيع الاشتراك بخدمه التجوال الدولي؟

**Detected language:** ar

**Answer:**
الخدمة فعالة تلقائياً لجميع اشتراكات الدفع المسبق. أما لمشتركي الاشتراكات الشهرية، فيرجى زيارة أقرب معرض أورنج لإيداع دفعة作为 شرط مسبق لتفعيل الخدمة.

**Sources:**
- `corpus/ar/international-roaming.html`

**Token usage:** 605 prompt + 47 completion = 652 total

---

### 5. ما هي خطوات اضافه اسم مستعار جديد؟

**Detected language:** ar

**Answer:**
أولاً، قم بتحديث تطبيق محفظه Orange Money ثم ادخل على المحفظة واضغط على "كليك" من القائمه الجانبيه. يمكنك اضافه اسم مستعار بصيغه ابجدي/رقمي او بريد اليكتروني ثم اضغط على حفظ. يمكنك اضافه 5 اسماء مستعاره على الاكثر وتحديد اسم رئيسي، مع امكانيه التحكم بتعطيل او الغاء الاسماء المستعاره.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 1147 prompt + 95 completion = 1242 total

---

### 6. بقدر احول المصاري لحساب بنك؟

**Detected language:** ar

**Answer:**
نعم، بتقدر ترسل المصاري لحساب بنكي إذا كان هاد الخيار متوفر ببلد المستقبل.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`

**Token usage:** 825 prompt + 27 completion = 852 total

---

### 7. هل يمكنني اضافه Google Pay على الساعه الذكيه؟ كيف؟

**Detected language:** ar

**Answer:**
نعم، يمكنك إضافة Google Pay على الساعة الذكية. قبل البدء، تأكد من توفر تطبيق Google Wallet على هاتفك ودعم ساعتك للميزة، وأنها مضافة مسبقاً هناك. ثم افتح التطبيق على الساعة، اضغط على "ابدأ"، فعّل قفل الشاشة إذا لزم الأمر، واتبع التعليمات لتأكيد الإضافة.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 1155 prompt + 72 completion = 1227 total

---

### 8. هل ساحتاج جهاز مودم جديد؟

**Detected language:** ar

**Answer:**
نعم، الأجهزة متوفرة مجاناً مع كل عروض Orange فايبر.

**Sources:**
- `corpus/ar/fiber-adsl.html`
- `corpus/en/fiber-adsl.html`
- `corpus/en/international-roaming.html`

**Token usage:** 463 prompt + 16 completion = 479 total

---

### 9. ماذا يحدث اذا ادخلت الرقم السري بشكل خاطئ عده مرات؟

**Detected language:** ar

**Answer:**
سيتم حظر حركات البطاقة التي تتطلب رقم سري (والتي تزيد عن 100 دينار) بعد 3 محاولات خاطئة.

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 806 prompt + 31 completion = 837 total

---

### 10. هل سيتوقف الاقتطاع اذا قمت بتنشيط محفظتي؟

**Detected language:** ar

**Answer:**
أجل سيٌتوقف الاقتطاع عند تنشيط المحفظة

**Sources:**
- `corpus/ar/orange-money.docx`
- `corpus/ar/orange-money.html`
- `corpus/en/orange-money.docx`
- `corpus/en/orange-money.html`

**Token usage:** 529 prompt + 16 completion = 545 total

---

## Summary

- Total questions tested: 20 (10 English + 10 Arabic)
- Failed requests: 0
- Total tokens consumed across all 20 requests: 13020
- Average tokens per request: 651