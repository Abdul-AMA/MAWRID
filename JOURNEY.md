# MAWRID — Research Journey

This file tracks every experiment, decision, and finding in chronological order. It is a living log — append new sections as the project progresses. The goal is to have a complete record of *why* we made each decision, not just *what* we built.

---

## Table of Contents

1. [Project Context](#1-project-context)
2. [Stage 1 — OCR (Current)](#2-stage-1--ocr-current)
   - [Attempt 1: PaddleOCR](#attempt-1-paddleocr)
   - [Attempt 2: Claude Haiku 4.5 Vision](#attempt-2-claude-haiku-45-vision)
   - [Attempt 3: EasyOCR](#attempt-3-easyocr-in-progress)
3. [Stage 2 — Classification](#3-stage-2--classification-not-started)
4. [Stage 3 — Extraction](#4-stage-3--extraction-not-started)
5. [Stage 4 — FormFill](#5-stage-4--formfill-not-started)
6. [Stage 5 — Validation](#6-stage-5--validation-not-started)
7. [Open Questions](#7-open-questions)
8. [Decision Log](#8-decision-log)

---

## 1. Project Context

**System:** MAWRID — AI-powered document intake system for the Municipality of Gaza.
**Dual purpose:** Production system + research paper comparing Arabic document AI pipeline configurations (called "combos").
**Test document used throughout Stage 1:** قرار رئيس بلدية غزة رقم 2025/14 — an Arabic government PDF with a multi-row table, numbered clauses, and mixed Latin/Arabic content.

### Pipeline Overview (5 stages)

```
Stage 1: OCR          ← we are here
Stage 2: Classification
Stage 3: Extraction
Stage 4: FormFill (deterministic)
Stage 5: Validation
```

All 10 combos share the same 5-stage pipeline. They differ only in which backend handles stages 1, 2, and 3. See `ARCHITECTURE.md` for the full combo map.

---

## 2. Stage 1 — OCR (Current)

**Goal:** Convert Arabic government PDFs into clean, structured text that downstream stages can reliably parse.
**Key challenge:** Arabic is RTL, cursive, and these documents are government scans — often low contrast, slight skew, dense table layouts.

---

### Attempt 1: PaddleOCR

**Date:** 2026-05-10
**Status:** Completed — results poor, still in use as the default local backend

#### Config used (`pipeline/ocr.py` line 16–23 — already in code)
```
lang:               'ar'   ← Arabic model, confirmed in code
use_angle_cls:      true
det_db_unclip_ratio: 2.25
det_db_thresh:       0.25
det_db_box_thresh:   0.5
```
Post-processing: custom `_fix_rtl()` (reverses Arabic strings) + `_merge_into_lines()` (groups word-boxes into lines, sorts RTL).

#### Results
| Metric | Result |
|--------|--------|
| Latency | 6.5 s |
| Cost | $0.00 (local) |
| Arabic word accuracy | Low (despite `lang='ar'`) |
| Table extraction | Failed completely |
| RTL ordering | Often reversed even with `_fix_rtl` |

#### Sample output (excerpt)
```
نوع القرار: قرارئيس بلدية
2025/14 القرار رقم Municipality of Gaza
التاريخ 4 :مارس02
1521(قرارقرئيسبرئي بلرغ
ارمات الكوارك تاري?/2 ت 0/تنا نلمت بللدية
```

#### Problems
- Words fused together: `قرارقرئيسبرئي`
- Random characters injected: `?`, `r`, mixed Latin in Arabic runs
- Dates broken: `تاري?/2 ت 0/`
- Table rows lost entirely — PaddleOCR returned flat noise where the table was
- RTL fix heuristic not sufficient for mixed-script lines

#### Root cause (revised)
`lang='ar'` was already set — the language model is not the issue. Problems are likely a combination of: low-DPI scan input, detection thresholds tuned for printed Latin text, and the Arabic recognition model struggling with dense cursive government document fonts.

#### What to try next
1. Tighten detection thresholds (`det_db_thresh` 0.25 → 0.35, `det_db_unclip_ratio` 2.25 → 1.8)
2. Preprocess images: upscale to ≥300 DPI + adaptive threshold (note: `_to_images` already renders at 300 DPI via PyMuPDF — check actual scan quality)
3. Try PP-OCRv4 server-grade model for maximum local accuracy

#### Why we kept it
PaddleOCR is the **only zero-cost, offline-capable** option. It is the default OCR backend in 8 of 10 combos. Getting it working is important for the research paper's offline/low-cost scenarios (combos L1, L3, H1C, H1G, H1Q, H1A, H2, H3).

---

### Attempt 2: Claude Haiku 4.5 Vision

**Date:** 2026-05-10
**Status:** Completed — excellent results, used in the `FL` and vision-test paths; too expensive for high volume as sole OCR

#### Config used
- Model: `claude-haiku-4-5`
- Mode: vision (raw PDF pages sent as images — NOT text)
- API: direct Anthropic SDK (not LiteLLM) for the vision endpoint
- Prompt: extract and structure the full document content

#### Results
| Metric | Result |
|--------|--------|
| Latency | 15.5 s |
| Cost per doc | ~$0.01 |
| Arabic word accuracy | High |
| Table extraction | Correct — full table reconstructed |
| RTL ordering | Correct throughout |
| Structure output | Full markdown with headers, numbered clauses, table |

#### Sample output (excerpt)
```markdown
| م. | الرقم | الاسم          | الوظيفة                        | المؤهل العلمي                            |
|----|-------|----------------|--------------------------------|------------------------------------------|
| 1  | 2705  | رشدي عاطف رشدي | كاتف بقسم الأمن والكوارث      | ماجستير في إدارة الأزمات والكوارث       |
```

#### Strengths
- Accurate Arabic word boundaries — no fused words
- Dates parsed cleanly: `24 مارس 2025`
- Table reconstructed with correct column alignment
- Document structure preserved: headers, numbered clauses, contact block
- No configuration required — works zero-shot

#### Weaknesses
- $0.01/doc × 10,000 docs/month = $100/month (vs $0 for local)
- Requires internet — no offline use
- Sends raw document images to a third-party API — data privacy consideration for sensitive government docs
- 15.5 s latency is 2.4× slower than PaddleOCR

#### Role in the system
- Used as the OCR in the `FL` combo (Frontier LLM — sends images to cloud)
- Powers the `/ocr/vision` debug endpoint and the `VisionOcrPage` in the frontend
- Acts as the **quality ceiling benchmark** — the best possible output we compare everything else against

---

### Attempt 3: Claude Opus Vision

**Date:** 2026-05-11
**Status:** Completed — highest quality output, highest cost; useful as absolute ceiling

#### Config used
- Model: `claude-opus-4` (or latest Opus)
- Mode: vision (raw PDF pages sent as images)
- Latency : **15.5 s**
- Cost per doc: **$0.04**
- Test document: قرار رئيس بلدية غزة رقم 2026/70 (employee retirement decision — different doc from Haiku test)

#### Sample output
```
| النوع: | قرار رئيس بلدية |
|--------|------------------|
| نوع القرار: | إنهاء خدمة |
| رقم القرار: | 2026/70 |

دولة فلسطين      بلدية غزة
Municipality of Gaza    State of Palestine

التاريخ: 13 ابريل، 2026م

قرار رئيس بلدية غزة رقم (2026/70)

بالاطلاع على ملف خدمة الموظف: عـودة خليـل يوسـف أبـو عمشـة، هويـة رقـم: 971070354 -
ملاحـظ صحة بقسم جمع وترحيل النفايات بـدائرة الصـحة والبيئـة- ...

تقرر

1. إنهـاء خدمـة الموظف: عـودة خليـل يوسـف أبـو عمشـة ...
2. يبدأ سريان هذا القرار اعتبارا من 2026/05/24م.
3. على جميع الجهات المختصة بالبلدية مراعاة تنفيذ هذا القرار ...

د. يحيى رشدي السراج
رئيس بلدية غزة

نسخة مع الاحترام لكلٍ من السادة:
- نائب رئيس البلدية.
- أمين سر المجلس البلدي.
...
```

#### Results
| Metric | Result |
|--------|--------|
| Cost per doc | **$0.04** |
| Arabic word accuracy | Excellent — word-perfect including diacritics on names |
| Table / header extraction | Correct — two-column header table preserved |
| Numbered clauses | Correct — all 3 clauses extracted in order |
| Signatories + distribution list | Correct — full CC list extracted |
| Contact block | Correct — phone, fax, address, URLs |

#### Comparison vs Haiku ($0.01)
| Dimension | Haiku | Opus |
|-----------|-------|------|
| Cost | $0.01 | $0.04 (4×) |
| Arabic accuracy | High | Excellent |
| Structured extraction | Good | Perfect |
| Distribution list | Partial | Complete |
| Worth the premium? | Default choice | Research ceiling only |

#### Role in the system
- Not used in any production combo — cost is prohibitive at scale
- Acts as the **absolute quality ceiling** above Haiku
- Useful for generating a gold-set ground truth for the research paper benchmark
- Confirms that vision-only LLM approach (no separate OCR stage) can achieve near-perfect accuracy

---

### Attempt 4: EasyOCR

**Date:** 2026-05-11
**Status:** Completed (baseline config) — mediocre results; better than PaddleOCR but far below Haiku
**Test document:** قرار رئيس بلدية غزة رقم 2026/70 (same as Opus test — direct comparison)

#### Why we tried it
EasyOCR uses a different detection architecture (CRAFT) and recognition backbone (CRNN) than PaddleOCR. It may handle Arabic cursive differently, especially with `paragraph=True` mode which attempts to preserve reading order.

#### Config used
Baseline defaults (Config A from sweep plan) — `['ar', 'en']`, `gpu=False`, `decoder='greedy'`

#### Sample output
```
النوع : قراررئيس بلدية
دولسة فلسطين بلديحة غزة نوع القرار : إنهاء خدمة
2026/70 رقم القرار : Municipality of Gaza State of Palestine

لتاريخ : 13 إبريل ن 2026
قراررئيس بلدية غزة رقم 70 2026

بالاطلاع على ملف خدمة الموظف: عودة خليل يوسف أبسو = عمشة  هوية رقم : . 971070354 - ملاحظ
صحة بقسم جمع وترحيل النفايات بدائرة الصحة والبيئة وحيث أن المذكور يبلغ السن القسانوني لإنهاء
الخدمة بتاريخ 2026/05/24 م فقد :

تقلد    ← WRONG: should be تقرر (critical error — changes meaning entirely)

.1 إنهاء خدمة الموظف: عسودة خليل يوسف أبسو _ عمشة ...
.2 يبدأ سريان هذا القرار اعتبارا من 2026/05/24
.3 على جميع الجهات المختصة بالبلدية مراعاة تنفيذ هذا القراركل فيما يخصه.

يحيى رشمي السراج    ← WRONG: should be رشدي
ئيس بلدية غزة       ← WRONG: missing ر (should be رئيس)
```

#### Results
| Metric | Result |
|--------|--------|
| Cost | $0.00 (local) |
| Latency | TBD |
| Document structure captured | Partial — main body present, table garbled |
| Critical word errors | Yes — `تقلد` instead of `تقرر` (completely changes meaning) |
| Name errors | Yes — `رشمي` instead of `رشدي`, `أبسو = عمشة` instead of `أبو عمشة` |
| Spurious characters | Yes — `=`, `_`, `.` injected into Arabic words |
| Contact block | Partial — `Munlcipمlii` garbled, rest mostly OK |

#### Specific errors catalogue
| Location | EasyOCR output | Correct text | Severity |
|----------|----------------|--------------|----------|
| Country name | `دولسة فلسطين` | `دولة فلسطين` | Minor |
| Municipality | `بلديحة غزة` | `بلدية غزة` | Minor |
| Date prefix | `لتاريخ` | `التاريخ` | Minor |
| Decision word | **`تقلد`** | **`تقرر`** | **Critical** |
| Legal term | `القسانوني` | `القانوني` | Moderate |
| Employee first name | `عسودة` | `عودة` | Moderate |
| Employee surname | `أبسو = عمشة` | `أبو عمشة` | Moderate |
| Mayor name | `رشمي` | `رشدي` | Moderate |
| Title | `ئيس بلدية` | `رئيس بلدية` | Moderate |

#### Assessment
EasyOCR baseline is clearly **better than PaddleOCR** (readable, structure present, numbers correct) but **not production-usable** without further tuning. The critical `تقلد`/`تقرر` confusion — a legal decision word — is disqualifying for government document processing at any confidence level.

#### Planned configs still to run (A through G sweep)
See `backend/experiments/ocr_comparison.md` for full parameter sweep. Configs B (beamsearch), C (mag_ratio), F (paragraph+beam) are the most likely to reduce character substitution errors.

| Config | Latency (s) | Arabic accuracy (1–5) | Table extracted | Notes |
|--------|------------|----------------------|-----------------|-------|
| A — Baseline | TBD | 2/5 | Partial | Tested above — critical word errors |
| B — Beamsearch | TBD | TBD | TBD | |
| C — mag_ratio 1.5 | TBD | TBD | TBD | |
| D — Aggressive detection | TBD | TBD | TBD | |
| E — Tight grouping | TBD | TBD | TBD | |
| F — Paragraph + beam | TBD | TBD | TBD | |
| G — GPU batch | TBD | TBD | TBD | |

---

### Attempt 5: Gemini Flash 2.5 Vision

**Date:** 2026-05-11
**Status:** Completed — good results, fastest cloud model tested; free tier severely limited
**Test document:** نموذج عهدة أجهزة حاسوب — equipment custody transfer form (Doc #74, different type from previous tests)
**Latency:** 12.7 s
**Cost:** Free tier — **20 RPD (requests per day) hard limit**, not viable for any production volume

#### Config used
- Model: `gemini-2.5-flash` (via Gemini API)
- Mode: vision (raw document image sent)
- Note: This is the `FL` combo's classifier/extractor model — here tested as a standalone OCR replacement

#### Sample output
```
So 74
التاريخ 2026/3/11

دولة فلسطين        بلدية غزة
State of Palestine Municipality of Gaza

نموذج ( ) تسجيل – ( ) تحويل – ( ) إتلاف ( ) عهدة شخصية

أجهزة حاسوب وملحقاتها

م  بيان العهدة (الصنف)  الموظف مسلم العهدة  توقيعه  الموظف مستلم العهدة  توقيعه  حالة العهدة
1  حاسوب 472  هاني ابو امرة  (Signature)
2
3
4
5
6
7
8
9

رقم الموظف 1763
تم الاستلام
(Signature)
م. الامداد
ع.ابو العسل
دائرة الرئيسي

نأمل اعتماد التغيير في العهد المذكورة أعلاه، وعمل ما يلزم حسب الأصول المتبعة.

(Signature)
رامي حسين
رئيس قسم الصيانة والدعم الفني

ملاحظات قسم العهد (فنية – إدارية): ...
لا مانع حسب الأصول المتبعة
مدير دائرة المخزن
```

#### Results
| Metric | Result |
|--------|--------|
| Latency | 12.7 s |
| Cost | Free (20 RPD limit) / paid tier TBD |
| Arabic word accuracy | Good — no critical substitutions |
| Form checkbox row | Preserved correctly |
| Table extraction | Correct — columns and rows identified, empty rows (2–9) preserved |
| Numbers | Correct (1763, 472, date) |
| Signature handling | Smart — renders handwritten signatures as `(Signature)` placeholder |
| Contact footer | Correct |
| RTL ordering | Correct throughout |

#### Noteworthy behavior
- **Signature placeholder:** Gemini chose to render handwritten signatures as `(Signature)` rather than attempting to transcribe them. This is the correct behavior for a government document processing system — signatures are not extractable text fields.
- **Empty table rows preserved:** Rows 2–9 were empty in the form and were correctly left empty (not hallucinated).
- **Different document type:** This is the first test on a form-style document (grid + checkboxes) vs. the decision letter used for PaddleOCR/Haiku/Opus/EasyOCR — showing Gemini handles both narrative and tabular form layouts.

#### Critical limitation
**20 RPD on the free tier** is unusable for anything beyond personal testing. At the municipality's expected volume this is a hard blocker unless we move to the paid API. The paid Gemini Flash 2.5 pricing needs to be checked and added here before considering it for production combos.

#### Role in the system
- Currently the OCR + classifier + extractor for the `FL` combo (sends images directly to Gemini)
- Now confirmed capable as a standalone vision OCR (good quality, ~Haiku level)
- Not yet cost-compared to Haiku on paid tier

---

### Stage 1 Summary — Current Standing

| Engine | Cost | Offline | Latency | Arabic Quality | Table Support | Status |
|--------|------|---------|---------|----------------|---------------|--------|
| PaddleOCR (`lang='ar'`) | Free | Yes | 6.5 s | Poor (1/5) | Failed | Tested — word fusion, garbled text |
| EasyOCR baseline | Free | Yes | TBD | Mediocre (2/5) | Partial | Tested — critical word errors |
| EasyOCR (tuned configs B–G) | Free | Yes | TBD | TBD | TBD | Sweep pending |
| Llama 4 Scout 17B Vision | TBD (API) | No | **2.7 s** | Good (3.5/5) | Correct | Tested — fastest model, minor name errors |
| Gemini Flash 2.5 Vision | Free (20 RPD) / paid TBD | No | 12.7 s | Good (3.5/5) | Correct | Tested — good quality, free tier too limited |
| Claude Haiku 4.5 Vision | ~$0.01/doc | No | 15.5 s | High (4/5) | Correct | Tested — cost-quality sweet spot |
| Claude Opus Vision | ~$0.04/doc | No | ~15 s | Excellent (5/5) | Perfect | Tested — absolute ceiling, gold-set only |

#### Quality ladder (confirmed)
```
PaddleOCR (local)        — poor (1/5)       — word fusion, garbled
        ↓
EasyOCR baseline (local) — mediocre (2/5)   — readable but critical substitutions
        ↓
EasyOCR tuned (local)    — TBD
        ↓
Llama 4 Scout 17B        — good (3.5/5)     — 2.7 s (!), minor name errors, cost TBD
Gemini Flash 2.5         — good (3.5/5)     — 12.7 s, free tier only (20 RPD), paid TBD
        ↓
Haiku Vision             — high (4/5)        — $0.01/doc, 15.5 s
        ↓
Opus Vision              — perfect (5/5)     — $0.04/doc  ← absolute ceiling
```

---

### Attempt 6: Llama 4 Scout 17B Vision (via API)

**Date:** 2026-05-11
**Status:** Completed — surprising quality at exceptional speed; a few name/abbreviation errors
**Test document:** قرار رئيس بلدية غزة رقم 2026/70 (same as Opus/EasyOCR — direct comparison)
**Model:** `llama-4-scout-17b-16e-instruct`
**Latency:** **2,701 ms (2.7 s)** — fastest of all tested models by a wide margin
**Cost:** TBD (depends on provider — likely Groq or Together AI)

#### Sample output
```
قرار رئيس بلدية
النوع:
نوع القرار: إنهاء خدمة
رقم القرار: 2026/70

التاريخ: 13 ابريل: 2026م

قرار رئيس بلدية غزة رقم (2026/70)

بالاطلاع على ملف خدمة الموظف: عودة خليل يوسف أبو عمشة، هوية رقم: 971070354 - ملاحظ صحة
بقسم جمع وترحيل النفايات بدائرة الصحة والبيئة - وحيث أن المذكور يبلغ السن القانوني لإنهاء
الخدمة بتاريخ 2026/05/24، فقد:

تقرر

1. إنهاء خدمة الموظف: عودة خليل يوسف أبو عمشة ...
2. يبدأ سريان هذا القرار اعتباراً من 2026/05/24.
3. على جميع الجهات المختصة بالبلدية ...

د. يحيى رفيق السراج    ← WRONG: should be رشدي (wrong middle name)
رئيس بلدية غزة

نسخة مع الاحترام لكلأمن السادة:    ← WRONG: should be لكلٍ من (garbled)
...
م.ج لشؤون الصحة والبيئة    ← WRONG: should be م.ع (wrong abbreviation)
...
0097050599815600    ← WRONG: extra digit (should be 00970599815600)
```

#### Results
| Metric | Result |
|--------|--------|
| Latency | **2.7 s** — 5.7× faster than Haiku, 4.7× faster than Gemini Flash |
| Cost | TBD (provider pricing) |
| Arabic word accuracy | Good — main body nearly perfect |
| Document structure | Correct — header table, numbered clauses, CC list all present |
| Critical word errors | None — `تقرر` correct (unlike EasyOCR) |
| Name/abbreviation errors | Yes — mayor middle name wrong, one abbreviation wrong |
| Numbers | Mostly correct — one phone number digit added |

#### Errors catalogue
| Location | Llama output | Correct (Opus) | Severity |
|----------|-------------|----------------|----------|
| Mayor middle name | `رفيق` | `رشدي` | Moderate — wrong person name |
| CC list header | `لكلأمن السادة` | `لكلٍ من السادة` | Minor — formatting |
| Department abbreviation | `م.ج` | `م.ع` | Moderate — wrong title |
| Phone number | `0097050599815600` | `00970599815600` | Minor — extra digit |

#### Assessment
Llama 4 Scout is the **speed champion** — 2.7 s vs 12–15 s for all cloud vision models. Quality is solid for the main document body (no critical word substitutions like EasyOCR's `تقلد`/`تقرر` disaster). The errors are in proper names and abbreviations — harder for any model to get right without context. For the hybrid approach (OCR text → LLM cleanup), Llama's raw text output at this speed is very attractive.

#### Role in the system
- Not currently in any combo — could replace Haiku as the LLM in H1C if cost/quality tradeoff favors it
- Strong candidate for a new **H1L combo** (PaddleOCR + Llama 4 Scout)
- Speed advantage makes it ideal for high-volume processing where Haiku latency is a bottleneck

---

#### Blocker: Azure DI dropped
Combos **AZ, H1A, H2, H3** all depend on Azure Document Intelligence. Azure requires a Visa card to register — not available. These combos are shelved. Active combo set is now: **L1, L3, FL, H1G, H1C, H1Q**.

#### Hybrid strategy (leading candidate for combos H1*)
Run PaddleOCR for text extraction, then pass the raw dirty text to Claude Haiku (text mode, not vision) to clean and structure it.
- Estimated cost: ~$0.003–0.005/doc (60–70% cheaper than Haiku vision mode)
- Estimated latency: ~8–10 s (PaddleOCR 6 s + short Haiku text call)
- Quality: likely near-Haiku level for Arabic accuracy + structure

---

## 3. Stage 2 — Classification (Not Started)

**Goal:** Given OCR text, identify which of the 91 document types it is.
**Planned backends:** ~~Azure DI Classifier~~ (blocked — see blocker below), AraBERT (zero-shot), AraBERT (fine-tuned), LLM (Gemini/Claude/Qwen)
**Current stub:** Always returns `"birth_certificate"` — hardcoded mock.

*Fill in when Stage 1 OCR is finalized and we begin classifier work.*

---

## 4. Stage 3 — Extraction (Not Started)

**Goal:** Given OCR text + document type, extract all schema fields as a structured dict.
**Planned backends:** ~~Azure DI Extractor~~ (blocked — see blocker below), LayoutLMv3 (zero-shot), LayoutLMv3 (fine-tuned), LLM
**Current stub:** Returns 8 hardcoded fields regardless of doc type.

*Fill in when Stage 2 Classification is finalized.*

---

## 5. Stage 4 — FormFill (Not Started as Experiment)

**Note:** FormFill is deterministic Python — not an ML stage. It maps extractor output keys to canonical schema field IDs. No experiments needed here; it just needs correct field mapping.

*Fill in if mapping issues surface during Stage 3 testing.*

---

## 6. Stage 5 — Validation (Not Started as Experiment)

**Note:** Validation computes a confidence score and flags low-confidence fields for human review. The heuristic is in place. Calibration may be needed once real extraction results come in.

*Fill in after first end-to-end run with real (non-mocked) stages.*

---

## 7. Open Questions

| # | Question | Blocking? | Answer |
|---|----------|-----------|--------|
| 1 | Does `lang='ar'` in PaddleOCR fix word-fusion and RTL ordering? | Yes | **No** — already set; problems are detection + model capability |
| 2 | Can EasyOCR beat PaddleOCR (ar) on cursive Arabic government docs? | No — research comparison | Baseline: yes, but still has critical word errors. Tuned configs pending |
| 3 | How much does PaddleOCR (ar) + Haiku text cleanup cost vs Haiku vision? | No — cost planning | TBD |
| 4 | Which combo wins on accuracy for the 91-doc gold set? | No — central research question | TBD |
| 5 | Is Claude sending document images over API acceptable under Gaza Municipality data policy? | Yes for FL combo usage | TBD |
| 6 | What is the paid Gemini Flash 2.5 price per document image? | Yes — needed before including it in any production combo | TBD |

---

## 8. Decision Log

Significant choices we made and why. Append when a non-obvious decision is locked in.

| Date | Decision | Rationale | Alternative considered |
|------|----------|-----------|------------------------|
| 2026-05-10 | Use Claude Haiku 4.5 as quality ceiling, not production OCR | Cost + offline requirement rules it out for high volume; excellent output makes it the benchmark | Using GPT-4o vision — ruled out: Anthropic SDK already integrated, lower cost |
| 2026-05-10 | Keep PaddleOCR as default local OCR despite poor results | Only zero-cost offline option; needed for L1/L3/H1* combos | Tesseract — ruled out: worse Arabic support, no RTL model |
| 2026-05-10 | Split pipeline into 5 discrete stages | Each stage swappable independently; enables combo comparison research | Monolithic LLM prompt — ruled out: can't isolate stage performance for the paper |
| 2026-05-10 | Use LiteLLM for all cloud LLM calls except Claude vision | Single interface for Gemini/Claude/Qwen; provider switch = one string change | Native SDKs per provider — ruled out: code duplication |
| 2026-05-11 | **Drop all Azure DI combos (AZ, H1A, H2, H3)** | Azure requires a Visa card for signup — not accessible. Combos AZ, H1A, H2, H3 are shelved until access is resolved | Prepaid card workaround — not pursued yet |

---

*Last updated: 2026-05-11*

---

## 9. Slide Summary — Stage 1 Progress

*4-slide snapshot for presentations. All data from experiments above.*

---

### Slide 1 — What is MAWRID?

**MAWRID** — AI document intake system for the Municipality of Gaza
Converts Arabic government PDFs → structured JSON fields, automatically.

| | |
|--|--|
| Document types | 91 types across 9 categories |
| Pipeline stages | 5 (OCR → Classify → Extract → FormFill → Validate) |
| Pipeline combos | 6 active (L1, L3, FL, H1G, H1C, H1Q) |
| Current stage | Stage 1 — OCR (ongoing) |
| Languages | Arabic RTL + English |

**The challenge:** Arabic is cursive, RTL, and government scans are dense — standard OCR tools fail badly.

---

### Slide 2 — OCR Engines Tested (6 so far)

| Engine | Type | Latency | Cost/doc | Quality |
|--------|------|---------|----------|---------|
| PaddleOCR | Local | 6.5 s | $0.00 | ⭐ (1/5) — word fusion, garbled |
| EasyOCR | Local | TBD | $0.00 | ⭐⭐ (2/5) — readable but critical errors |
| Llama 4 Scout 17B | Cloud API (Groq) | **2.7 s** | ~free | ⭐⭐⭐½ (3.5/5) — fast, minor name errors |
| Gemini Flash 2.5 | Cloud API | 12.7 s | free (20 RPD) | ⭐⭐⭐½ (3.5/5) — good, limited free tier |
| Claude Haiku 4.5 | Cloud API | 15.5 s | $0.01 | ⭐⭐⭐⭐ (4/5) — high quality |
| Claude Opus | Cloud API | ~15 s | $0.04 | ⭐⭐⭐⭐⭐ (5/5) — perfect, gold standard |

**6 engines tested · 2 local · 4 cloud · 1 blocked (Azure — no Visa card)**

---

### Slide 3 — Speed vs Quality vs Cost

```
         QUALITY
            5 │                              ● Opus ($0.04)
              │
            4 │                    ● Haiku ($0.01)
              │
          3.5 │  ● Llama (2.7s)    ● Gemini (12.7s)
              │
            2 │  ● EasyOCR
              │
            1 │  ● PaddleOCR
              └─────────────────────────────────────
                  FREE              $0.01         $0.04
                              COST / DOC
```

**Key finding:** Llama 4 Scout sits at the same quality tier as Gemini Flash but runs **4.7× faster** (2.7 s vs 12.7 s) on Groq's free tier — making it the best value option discovered so far.

**Cost projection at 1,000 docs/month:**

| Strategy | Monthly cost |
|----------|-------------|
| PaddleOCR only | $0 |
| Llama 4 Scout (Groq) | ~$0 (free tier) |
| Haiku vision only | ~$10 |
| Opus vision only | ~$40 |
| Hybrid (PaddleOCR + Haiku text) | ~$4 |

---

### Slide 4 — What's Next

**Stage 1 remaining:**
- [ ] EasyOCR tuned configs (B–G sweep) — beamsearch + magnification
- [ ] Confirm Llama 4 Scout paid pricing on Groq
- [ ] Confirm Gemini Flash 2.5 paid pricing
- [ ] Choose final OCR strategy for each combo before moving to Stage 2

**Stage 2 (Classification) — up next:**
- AraBERT zero-shot → fine-tuned
- LLM-based classification (Gemini / Claude / Llama)
- Target: correctly identify all 91 document types from OCR text alone

**Stage 3 (Extraction) — after that:**
- LayoutLMv3 zero-shot → fine-tuned
- LLM-based field extraction
- Target: extract all schema fields with ≥ 0.85 confidence average

**Dropped:**
- Azure DI (AZ, H1A, H2, H3 combos) — requires Visa card, not available
