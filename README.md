<div align="center">

# مَوْرِد · MAWRID

**AI-Powered Arabic Document Intake System**  
*Built for the Municipality of Gaza · بلدية غزة*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![MLflow](https://img.shields.io/badge/MLflow-2.13-0194E2?logo=mlflow&logoColor=white)](https://mlflow.org)

</div>

---

## What is MAWRID?

MAWRID converts Arabic government PDFs into structured JSON — automatically. It is simultaneously a **production intake system** and a **research platform** comparing 6+ pipeline configurations (called "combos") for Arabic document AI.

The central challenge: Arabic is cursive, right-to-left, and government scans are dense with tables, numbered clauses, and mixed scripts. Standard OCR tools fail badly. MAWRID tests every serious approach and measures them all.

```
Arabic PDF  →  OCR  →  Classify  →  Extract  →  FormFill  →  Validate  →  JSON
              Stage 1    Stage 2      Stage 3      Stage 4      Stage 5
```

**91 document types** across 9 categories — health files, employee evaluations, academic credentials, CVs, disciplinary records, employment procedures, correspondence, personal documents, and administrative orders.

---

## Pipeline Combos

The combo system is the research core. A **combo** selects which backend runs each of the 3 ML stages. Switching is a single env var — no code changes, no restarts.

| Combo | Stage 1 — OCR | Stage 2 — Classify | Stage 3 — Extract | Character |
|-------|--------------|---------------------|-------------------|-----------|
| **L1** | PaddleOCR | AraBERT zero-shot | LayoutLMv3 zero-shot | Pure local, no cloud |
| **L3** | PaddleOCR | AraBERT fine-tuned | LayoutLMv3 fine-tuned | Fully trained local |
| **FL** | Gemini Vision | Gemini 2.0 Flash | Gemini 2.0 Flash | Frontier LLM, sends images |
| **H1G** | PaddleOCR | Gemini 2.0 Flash | Gemini 2.0 Flash | Hybrid: local OCR + Gemini |
| **H1C** | PaddleOCR | Claude Haiku | Claude Haiku | Hybrid: local OCR + Claude |
| **H1Q** | PaddleOCR | Qwen Max | Qwen Max | Hybrid: local OCR + Qwen |

Switch combos via API — no restart required:
```bash
curl -X POST http://localhost:8000/api/combos/set -d '{"combo": "H1C"}'
```

---

## OCR Research Findings

Stage 1 has been the hardest problem. Here is what we found testing 6 engines on real Gaza Municipality documents:

| Engine | Type | Latency | Cost/doc | Arabic Quality |
|--------|------|---------|----------|----------------|
| PaddleOCR | Local | 6.5 s | $0.00 | ⭐ — word fusion, garbled |
| EasyOCR | Local | ~8 s | $0.00 | ⭐⭐ — critical word errors |
| Llama 4 Scout 17B | Cloud (Groq) | **2.7 s** | ~free | ⭐⭐⭐½ — fast, minor name errors |
| Gemini Flash 2.5 | Cloud | 12.7 s | free/paid | ⭐⭐⭐½ — good quality |
| Claude Haiku 4.5 | Cloud | 15.5 s | $0.01 | ⭐⭐⭐⭐ — high quality |
| Claude Opus | Cloud | ~15 s | $0.04 | ⭐⭐⭐⭐⭐ — perfect (gold standard) |

**Key finding:** Llama 4 Scout on Groq delivers near-Haiku quality at **5.7× the speed** and near-zero cost — making it the most attractive hybrid option for production volume.

**Cost at 1,000 docs/month:**

| Strategy | Monthly cost |
|----------|-------------|
| PaddleOCR only | $0 |
| Llama 4 Scout (Groq) | ~$0 (free tier) |
| Hybrid (PaddleOCR + Haiku text) | ~$4 |
| Claude Haiku vision only | ~$10 |
| Claude Opus vision only | ~$40 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│  Upload → Process → Review → Save   │   Experiments Dashboard   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────────────┐
│                       BACKEND (FastAPI)                          │
│  POST /upload → create Job → enqueue Celery → return job_id     │
│  WS /ws/jobs/:id → real-time stage-by-stage progress            │
└──────────────────────┬──────────────────────────────────────────┘
                       │ Celery task dispatch
┌──────────────────────▼──────────────────────────────────────────┐
│                      CELERY WORKER                               │
│   Stage 1: OCR  →  Stage 2: Classify  →  Stage 3: Extract      │
│   Stage 4: FormFill  →  Stage 5: Validate                       │
└──────┬────────────────┬─────────────────┬───────────────────────┘
       │                │                 │
  ┌────▼────┐    ┌──────▼─────┐   ┌──────▼──────┐
  │  Redis  │    │  SQLite/PG │   │   MLflow    │
  │(broker) │    │  (results) │   │ (tracking)  │
  └─────────┘    └────────────┘   └─────────────┘
```

Every pipeline run is logged to **both MLflow and SQLite** simultaneously — MLflow for visual comparison dashboards, SQLite for instant API queries.

---

## Tech Stack

### Backend
| | Technology | Role |
|--|------------|------|
| 🐍 | Python 3.11 + FastAPI | Async API server, auto-generated OpenAPI docs |
| ⚡ | Celery + Redis | Async task queue — OCR/inference never blocks the API |
| 🗄️ | SQLAlchemy 2.0 (async) | ORM — one env var switches SQLite (dev) → PostgreSQL (prod) |
| 🔤 | PaddleOCR + EasyOCR | Local Arabic OCR engines |
| 📄 | PyMuPDF | PDF → high-DPI image conversion |
| 🤖 | LiteLLM | Unified gateway to Gemini, Claude, Qwen, Ollama, 100+ providers |
| 🧠 | HuggingFace Transformers | AraBERT (classify) + LayoutLMv3 (extract) |
| 📊 | MLflow | Experiment tracking, run comparison, metric visualization |
| ⚙️ | Pydantic Settings | Type-safe config — combo hot-switch via `settings.cache_clear()` |

### Frontend
| | Technology | Role |
|--|------------|------|
| ⚛️ | React 18 + TypeScript | UI framework with concurrent mode |
| ⚡ | Vite | 10× faster dev server than CRA/Webpack |
| 🎨 | Tailwind CSS + Radix UI | Utility styling + accessible headless components |
| 🔄 | React Query | Job status polling, caching, and invalidation — no Redux needed |
| 🌐 | RTL/LTR toggle | Full Arabic right-to-left support throughout |

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- API keys for your chosen combo (Anthropic, Groq, or Google)

### Run with Docker

```bash
git clone https://github.com/Abood-AMA/MAWRID.git
cd MAWRID
cp .env.example .env
# Fill in your API keys in .env
docker compose up
```

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | React UI |
| Backend API | http://localhost:8000/docs | FastAPI + Swagger |
| MLflow | http://localhost:5000 | Experiment dashboard |

### Environment Variables

```env
# Choose your active combo
MAWRID_COMBO=H1C

# API keys (only the ones your combo needs)
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...

# Database (SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite+aiosqlite:///./mawrid.db
```

---

## API Reference

### Core Pipeline

```
POST /api/documents/upload     Upload PDF, start processing, get job_id
GET  /api/documents/{job_id}   Poll job status + result
WS   /ws/jobs/{job_id}         Real-time stage-by-stage progress
```

### Combo Management

```
GET  /api/combos               List all combos + active combo
POST /api/combos/set           Hot-switch active combo (no restart)
```

### Experiments

```
GET  /api/experiments          Paginated MLflow run history
POST /api/experiments/compare  Diff two runs side-by-side
```

### OCR Debug Tools

```
POST /api/ocr/run              Run PaddleOCR or EasyOCR standalone
POST /api/ocr/vision           Claude vision OCR (direct Anthropic API)
GET  /api/schema               Full 91-doc-type schema
GET  /health                   Health check + active combo
```

---

## Frontend Pages

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Process | Upload PDF → run pipeline → review fields → save |
| `/saved` | Saved Records | Browse and manage verified documents |
| `/experiments` | Experiments | Compare MLflow runs across combos |
| `/ocr` | OCR Debug | Test PaddleOCR configurations standalone |
| `/ocr-vision` | Vision OCR | Test Claude vision OCR quality |

---

## Document Schema

`config/schema_v2.json` defines all 91 document types across 9 categories. It drives classification, extraction, field rendering, and storage.

**9 Categories:**

| Arabic | Category |
|--------|----------|
| الملف الصحي | Health Files |
| تقييم الموظف | Employee Evaluation |
| المؤهلات الأكاديمية | Academic Credentials |
| السيرة الذاتية | CVs |
| التأديبية | Disciplinary Records |
| إجراءات التوظيف | Employment Procedures |
| المراسلات | Correspondence |
| الوثائق الشخصية | Personal Documents |
| الأوامر الإدارية | Administrative Orders |

---

## Project Status

| Stage | Status | Notes |
|-------|--------|-------|
| Stage 1 — OCR | 🔄 Active | 6 engines tested; PaddleOCR + cloud vision working |
| Stage 2 — Classify | ⏳ Next | Stub returns `birth_certificate`; AraBERT + LLM incoming |
| Stage 3 — Extract | ⏳ Pending | Stub returns hardcoded fields; LayoutLMv3 + LLM incoming |
| Stage 4 — FormFill | ✅ Done | Deterministic Python schema mapper |
| Stage 5 — Validate | ✅ Done | Confidence heuristic + low-confidence flagging |
| Infrastructure | ✅ Done | Docker, Celery, Redis, MLflow, WebSocket, hot combo-switch |
| Frontend | ✅ Done | All 5 pages, full Arabic RTL, experiments dashboard |
| Benchmark suite | 🔄 Design | Claude as GT oracle; Groq + Ollama as competitors |

---

## Research Context

MAWRID is the subject of a comparative study on Arabic document AI pipelines. The benchmark will:

1. Use **Claude Opus** to generate ground truth — structured extraction on 15 real Gaza Municipality documents
2. Run all 6 combos on the same documents
3. Score each combo on: classification accuracy, field F1, value accuracy (Arabic-normalized), and latency per stage
4. Produce a cost-quality-speed tradeoff analysis across local, hybrid, and frontier LLM approaches

See [`JOURNEY.md`](JOURNEY.md) for the full experimental log and [`ARCHITECTURE.md`](ARCHITECTURE.md) for the complete technical reference.

---

## Why "MAWRID"?

**مَوْرِد** (mawrid) means *a source* or *a resource* in Arabic — a place you go to get what you need. The system is designed to be exactly that: the entry point through which every document flows before it enters the municipality's records.

---

<div align="center">

Built with care for Gaza · بُني بعناية لغزة

</div>
