---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
  }
  h1 { color: #38bdf8; font-size: 1.8em; border-bottom: 2px solid #38bdf8; padding-bottom: 0.2em; }
  h2 { color: #7dd3fc; }
  h3 { color: #38bdf8; }
  table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
  th { background: #1e3a5f; color: #7dd3fc; padding: 6px 10px; text-align: left; }
  td { padding: 5px 10px; border-bottom: 1px solid #1e3a5f; }
  tr:nth-child(even) td { background: #0f2035; }
  code { background: #1e293b; color: #7dd3fc; padding: 2px 6px; border-radius: 4px; }
  strong { color: #f0abfc; }
  ul li { margin-bottom: 4px; }
  .highlight { color: #34d399; font-weight: bold; }
  footer { color: #475569; font-size: 0.7em; }
---

# MAWRID — Stage 1 Progress
## OCR Engine Research · May 2026

AI-powered Arabic Document Intake System
**Municipality of Gaza**

---

# What is MAWRID?

Converts Arabic government PDFs → structured JSON fields, automatically.

| | |
|---|---|
| Document types | **91 types** across 9 categories |
| Pipeline stages | **5** (OCR → Classify → Extract → FormFill → Validate) |
| Active combos | **6** pipeline configurations under comparison |
| Current stage | **Stage 1 — OCR** (ongoing) |
| Languages | Arabic RTL + English |

**The challenge:** Arabic is cursive, RTL, and government scans are dense — standard OCR tools fail badly out of the box.

---

# 6 OCR Engines Tested

| Engine | Type | Latency | Cost/doc | Quality |
|--------|------|---------|----------|---------|
| PaddleOCR | Local | 6.5 s | $0.00 | ⭐ — word fusion, garbled |
| EasyOCR | Local | TBD | $0.00 | ⭐⭐ — readable, critical errors |
| Llama 4 Scout 17B | API (Groq) | **2.7 s** | ~free | ⭐⭐⭐½ — fast, minor name errors |
| Gemini Flash 2.5 | API (Google) | 12.7 s | free (20 RPD) | ⭐⭐⭐½ — good, limited free tier |
| Claude Haiku 4.5 | API (Anthropic) | 15.5 s | **$0.01** | ⭐⭐⭐⭐ — high quality |
| Claude Opus | API (Anthropic) | ~15 s | $0.04 | ⭐⭐⭐⭐⭐ — perfect · gold standard |

**2 local · 4 cloud · 1 blocked** (Azure — Visa card required)

---

# Speed · Quality · Cost

| Engine | Latency | Quality | Cost/doc |
|--------|---------|---------|----------|
| **Llama 4 Scout** | **2.7 s** | ⭐⭐⭐½ | ~$0.00 |
| Gemini Flash 2.5 | 12.7 s | ⭐⭐⭐½ | ~$0.00 * |
| Claude Haiku 4.5 | 15.5 s | ⭐⭐⭐⭐ | $0.01 |
| Claude Opus | ~15 s | ⭐⭐⭐⭐⭐ | $0.04 |

*\* 20 requests/day free tier limit*

**Llama 4 Scout is 4.7× faster than Gemini Flash at the same quality.**

### Cost at 1,000 docs/month
| Strategy | Monthly cost |
|----------|-------------|
| PaddleOCR only (local) | $0 |
| Hybrid: PaddleOCR + Haiku text cleanup | ~$4 |
| Haiku vision only | ~$10 |
| Opus vision only | ~$40 |

---

# What's Next

### Stage 1 — Remaining
- EasyOCR tuned configs (beamsearch + magnification sweep)
- Confirm Llama 4 Scout & Gemini Flash paid pricing
- Lock final OCR backend per combo

### Stage 2 — Classification
Identify document type from OCR text alone (91 types)
→ AraBERT · LLM-based (Gemini / Claude / Llama)

### Stage 3 — Extraction
Pull all schema fields from text + doc type
→ LayoutLMv3 · LLM-based

### Dropped
~~Azure DI (AZ, H1A, H2, H3 combos)~~ — requires Visa card
