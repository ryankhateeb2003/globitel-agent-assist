# Arabic Fluency Review

## Method

The task brief requires a human review specifically for Arabic naturalness, separate from the general judge-validation pass, because "an LLM judge is weaker at judging Arabic fluency than at judging English fluency" and should not be assumed accurate on its own.

A random sample of 15 Arabic answers was drawn from the 32 Arabic answerable items in `answer_quality_raw.json` (seed=43, `arabic_fluency_sample.json`). Each answer was read against one question only: **"If a Jordanian customer service agent said this out loud on a call, would it sound natural -- or would it sound like a stiff, word-for-word translation?"** -- per the task brief's own framing ("Arabic that a Jordanian agent would not say aloud to a customer, has failed even if the facts are right"). This is about register and naturalness, not about requiring Jordanian dialect -- correct, simplified spoken-register Modern Standard Arabic is the target, not colloquial Ammiya.

**Reviewer note:** This pass was done by  ryan then  i i let Claude (AI-assisted) check , not a native-Arabic-speaking human colleague as the task brief's letter specifies. It should be treated as a useful independent signal, not a substitute for a native speaker's final sign-off -- flagged here honestly rather than presented as full compliance with the brief's requirement.

---

## Summary

| Verdict | Count | Share |
|---|---:|---:|
| Natural -- an agent would say this as-is | 11 | 73% |
| Slightly formal/listy, but acceptable | 3 | 20% |
| Genuinely unnatural (would not be said aloud) | 1 | 7% |

**Explanation:** The large majority of sampled Arabic answers read as natural, spoken-register Arabic a real agent could use directly. The 3 "slightly formal" cases are answers whose phrasing leans technical/written-register rather than conversational, but are still understandable and usable on a call. Only 1 of 15 has a genuine fluency problem worth fixing.

---

## Item-by-item

| # | ID | Verdict | Answer (excerpt) | Note |
|---|---|---|---|---|
| 1 | `ar-exact-003` | Natural | "اتصل على *112# لوقف الرسائل الدعائية." | Short, natural imperative. (Judge scored this 0.7, flagging "لوقف" vs "لإيقاف" -- disagree, "لوقف" is normal spoken usage, not stiff.) |
| 2 | `ar-simple-013` | Natural | "مدة صلاحية القسائم الإلكترونية 6 أشهر من وقت الشراء." | Clean, simple, natural factual statement. |
| 3 | `ar-multi-014` | Natural | "لعرض تفاصيل القسائم... أما إذا لم تظهر القسيمة بعد الشراء، يرجى الاتصال..." | Natural connector usage ("أما إذا"). |
| 4 | `ar-multi-016` | Natural | "سجّل الدخول... واختر... ثم حدد... واضغط..." | Natural step-by-step imperative flow, how a real agent would list steps. |
| 5 | `ar-exact-008` | Natural | "تقدر تحوّل المصاري من محفظتك لمحفظة أخرى عن طريق تطبيق Orange Money..." | Natural spoken-register mix ("تقدر تحوّل") -- reads like real customer service speech. |
| 6 | `ar-simple-018` | Natural | "يمكنك الوصول إلى تفاصيل الفاتورة من خلال تسجيل الدخول إلى خدمة Orange ecare." | Short, natural. |
| 7 | `ar-simple-015` | Slightly formal | "...من خلال زيارة أحد معارضنا المنتشرة في المملكة..." | Judge flagged this (0.7) -- reasonable but a bit harsh; this phrasing is common in Jordanian corporate customer-service Arabic, not glaringly stiff. |
| 8 | `ar-multi-013` | Natural | "شغّل موبايلك وسيسجّل تلقائيًا على الشبكة المناسبة..." | Natural. |
| 9 | `ar-shortcode-001` | Natural | "اضغط *606# لتفعيل خدمة الرصيد الطارئ." | Natural, short. |
| 10 | `ar-exact-004` | Natural | "لا، لا تحتاج إلى موبايل ذكي... وكل ما تحتاجه هو رقم خلوي فعال." | Natural. |
| 11 | `ar-dialect-002` | **Unnatural** | "يمكنك سداد فواتير عروض الجوال والثابت والانترنت في كل مكان و ADSL / الالياف وبيت العيله المتقاربه." | **Real issue**, but not the one the judge named (judge flagged "بيت العيله المتقاربه" specifically as confusing -- that part is a verbatim service/bundle name from the source, not the real problem). The actual issue is the **sentence structure**: several distinct service names strung together with "و" as a run-on list, reading like a copied bullet list rather than a spoken sentence. A natural version would break this into a short list or add connective phrasing. |
| 12 | `ar-multi-011` | Natural | "نعم، الخدمة متوفرة لمشتركي خدمة الفايبر الجدد الذين لا يملكون خطاً أرضياً..." | Natural. |
| 13 | `ar-simple-019` | Slightly formal | "جهاز المودم لاسلكي، وهو متوفر مع جميع الحزم." | Judge flagged this (0.7) -- "متوفر مع جميع الحزم" is standard, common phrasing; disagree with the low score, though the sentence is a touch flat/technical rather than conversational. |
| 14 | `ar-exact-001` | Slightly formal | "...وتتميز بسعة تحميل غير محدودة وتجربة متميزة في استخدام جميع التطبيقات." | Judge flagged "سعة تحميل غير محدودة" (0.6) -- disagree, this is standard telecom/marketing Arabic, not unnatural; register is simply more written/promotional than conversational. |
| 15 | `ar-simple-020` | Natural | "يمكنك التحقق من الرصيد المتبقي لسقف الاستهلاك وصلاحيته عبر تطبيق Max it أو بالاتصال على *979#." | Natural. |

---

## Conclusion

- **93% (14/15)** of sampled Arabic answers are either fully natural or acceptable-if-slightly-formal -- usable as-is on a live call.
- **1 genuine fluency defect found** (`ar-dialect-002`): run-on concatenation of service names copied from the source's list structure, rather than a natural spoken sentence. This is a **generation-prompt-level fix opportunity** (instruct the model to convert list-style context into natural spoken phrasing, not concatenate it with "و").
- Cross-checked against `judge_language_correctness` scores for these same 15 items: the judge's low scores on 3 items (`ar-exact-003`, `ar-simple-019`, `ar-exact-001`) appear **overly harsh** -- consistent with `judge-validation.md`'s finding that the judge's Arabic-fluency judgment is measurably less reliable than its other checks.
