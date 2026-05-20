# MAWRID — Architecture Reference

MAWRID is an AI-powered document intake and processing system built for the Municipality of Gaza. It is simultaneously a **production system** and a **research platform** — every architectural decision is designed to be production-grade and fully traceable for comparative research on Arabic document AI pipelines.

---

## Table of Contents

1. [Project Goals](#1-project-goals)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Tech Stack & Why](#3-tech-stack--why)
4. [Pipeline Stages](#4-pipeline-stages)
5. [Combo System](#5-combo-system)
6. [Data Flow (End to End)](#6-data-flow-end-to-end)
7. [API Reference](#7-api-reference)
8. [Database Schema](#8-database-schema)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Infrastructure & Docker](#10-infrastructure--docker)
11. [Document Schema](#11-document-schema)
12. [Experiment Tracking](#12-experiment-tracking)
13. [Key Design Decisions](#13-key-design-decisions)
14. [Current Status & Roadmap](#14-current-status--roadmap)

---

## 1. Project Goals

| Goal | Detail |
|------|--------|
| **Production** | Receive Arabic  PDFs, extract structured fields, return JSON |
| **Research** | Compare 10 pipeline configurations (combos) side-by-side with measurable metrics |
| **Bilingual** | Full Arabic RTL + English LTR support throughout UI and schema |
| **Modular** | Swap OCR, classifier, or extractor backends with a single env var change |

**Document types covered:** 91 Arabic  document types across 9 categories (health files, employee evaluation, academic credentials, CVs, disciplinary records, employment procedures, correspondence, personal documents, administrative orders).

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│  Upload → Process → Review → Save   │   Experiments Dashboard   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────────────┐
│                       BACKEND (FastAPI)                          │
│  POST /upload → create Job → enqueue Celery task → return job_id│
│  GET /job/:id → poll status + result                            │
│  WS  /ws/jobs/:id → real-time stage updates                     │
└──────────────────────┬──────────────────────────────────────────┘
                       │ Celery task dispatch
┌──────────────────────▼──────────────────────────────────────────┐
│                      CELERY WORKER                               │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Pipeline Runner                        │   │
│   │  Stage 1: OCR → Stage 2: Classify → Stage 3: Extract   │   │
│   │  Stage 4: FormFill → Stage 5: Validate                 │   │
│   └─────────────────────────────────────────────────────────┘   │
└──────┬────────────────┬─────────────────┬───────────────────────┘
       │                │                 │
  ┌────▼────┐    ┌──────▼─────┐   ┌──────▼──────┐
  │  Redis  │    │  SQLite/PG │   │   MLflow    │
  │(broker) │    │  (results) │   │ (tracking)  │
  └─────────┘    └────────────┘   └─────────────┘
```

---

## 3. Tech Stack & Why

### Backend

| Technology | Version | Role | Why |
|------------|---------|------|-----|
| **Python** | 3.11 | Runtime | Mature ML ecosystem; async support |
| **FastAPI** | 0.111.0 | Web framework | Native async, auto-generated OpenAPI docs, Pydantic integration |
| **Uvicorn** | latest | ASGI server | Fastest Python ASGI server for FastAPI |
| **SQLAlchemy** | 2.0 (async) | ORM | First-class async support; single `DATABASE_URL` switch between SQLite and PostgreSQL |
| **SQLite** (dev) / **PostgreSQL** (prod) | — | Database | SQLite for zero-config dev; PostgreSQL for production via single env var swap |
| **Celery** | 5.4.0 | Task queue | Offload CPU-heavy OCR and inference from the API process; horizontal scaling |
| **Redis** | 5.0.7 | Message broker + result store | Standard Celery backend; also used for job result caching |
| **PaddleOCR** | 2.7.3 | OCR engine | Best open-source Arabic OCR performance; runs fully locally; RTL-aware |
| **EasyOCR** | latest | OCR fallback | Backup to PaddleOCR for edge cases |
| **PyMuPDF** | 1.24.5 | PDF processing | Fast PDF→image conversion; used to feed pages to OCR |
| **LiteLLM** | 1.41.27 | Unified LLM gateway | Single interface for Gemini, Claude, Qwen without changing code per provider |
| **Anthropic SDK** | ≥0.40.0 | Claude vision OCR | Direct Claude API access for vision-based OCR in the H1C combo |
| **Azure Document Intelligence** | 3.3.3 | Cloud OCR + classification | Microsoft's best-in-class Arabic document AI; used in AZ and hybrid combos |
| **HuggingFace Transformers** | 4.41.2 | Local models | AraBERT (classification) + LayoutLMv3 (extraction) |
| **PyTorch** | 2.3.1 | ML runtime | Required by HuggingFace models |
| **Sentence Transformers** | latest | Embeddings | Semantic similarity for field matching |
| **MLflow** | 2.13.2 | Experiment tracking | Log every run with full metrics; compare combos visually |
| **Pydantic Settings** | 2.3.0 | Config management | Type-safe env var parsing; `.env` file support; runtime cache clearing for combo switching |

### Frontend

| Technology | Version | Role | Why |
|------------|---------|------|-----|
| **React** | 18 | UI framework | Industry standard; concurrent mode for smooth UX |
| **TypeScript** | 5.4.5 | Type safety | Catches API contract mismatches at compile time |
| **Vite** | 5.3.1 | Build tool | 10× faster dev server than CRA/Webpack; instant HMR |
| **Tailwind CSS** | 3.4.4 | Styling | Utility-first; no CSS files to maintain; RTL works naturally |
| **Radix UI** | latest | Headless components | Accessible, unstyled primitives (dialogs, dropdowns, tabs, toast) |
| **React Query** | 5.40.0 | Server state | Automatic polling, caching, and invalidation for job status |
| **React Router** | 6.23.1 | Client routing | 5-page SPA (process, saved, experiments, ocr, vision-ocr) |
| **Axios** | 1.7.2 | HTTP client | Interceptors for auth headers; request/response typing |
| **Lucide React** | latest | Icons | Consistent icon set matching Radix UI style |

---

## 4. Pipeline Stages

Every document processed by MAWRID passes through 5 sequential stages:

```
File bytes
    │
    ▼
┌──────────────────────────────────┐
│  Stage 1 — OCR                   │
│  PDF pages → images → raw text   │
│  Backends: PaddleOCR, Azure DI   │
└──────────────┬───────────────────┘
               │ raw Arabic text
               ▼
┌──────────────────────────────────┐
│  Stage 2 — Classify              │
│  raw text → document type ID     │
│  Backends: AraBERT, Azure, LLM   │
└──────────────┬───────────────────┘
               │ doc_type (e.g. "birth_certificate")
               ▼
┌──────────────────────────────────┐
│  Stage 3 — Extract               │
│  raw text + doc_type → field dict│
│  Backends: LayoutLMv3, Azure, LLM│
└──────────────┬───────────────────┘
               │ {field_id: value, ...}
               ▼
┌──────────────────────────────────┐
│  Stage 4 — FormFill              │
│  Map extracted fields to schema  │
│  Pure Python (no ML, deterministic)│
└──────────────┬───────────────────┘
               │ canonical FormResult
               ▼
┌──────────────────────────────────┐
│  Stage 5 — Validate              │
│  Confidence scoring              │
│  Flag low-confidence fields      │
└──────────────┬───────────────────┘
               │ PipelineResult
               ▼
          API Response
```

**Key constraint:** OCR text only is sent to cloud LLMs — never raw page images, **except** in the `FL` (Frontier LLM) combo where Gemini receives images directly for vision-based processing.

---

## 5. Combo System

The combo system is the central research mechanism. A **combo** is a named configuration of 3 backend choices (OCR + Classifier + Extractor) set via the `MAWRID_COMBO` environment variable. Switching combos requires no code change and no server restart.

### Combo Map

| Combo | OCR | Classifier | Extractor | Character |
|-------|-----|------------|-----------|-----------|
| **L1** | PaddleOCR | AraBERT zero-shot | LayoutLMv3 zero-shot | Pure local, no cloud |
| **L3** | PaddleOCR | AraBERT fine-tuned | LayoutLMv3 fine-tuned | Fully trained local |
| **AZ** | Azure DI Read | Azure Classifier | Azure Extractor | Pure cloud (Microsoft) |
| **FL** | Vision (Gemini) | Gemini 2.0 Flash | Gemini 2.0 Flash | Frontier LLM, sends images |
| **H1G** | PaddleOCR | Gemini 2.0 Flash | Gemini 2.0 Flash | Hybrid: local OCR + Gemini |
| **H1C** | PaddleOCR | Claude Haiku | Claude Haiku | Hybrid: local OCR + Claude *(active)* |
| **H1Q** | PaddleOCR | Qwen Max | Qwen Max | Hybrid: local OCR + Qwen |
| **H1A** | PaddleOCR | Azure Classifier | Azure Extractor | Hybrid: local OCR + Azure AI |
| **H2** | PaddleOCR | AraBERT fine-tuned | Gemini 2.0 Flash | Mixed: best local classify |
| **H3** | PaddleOCR | AraBERT fine-tuned | Azure Extractor | Mixed: local classify, Azure extract |

### Backend Routing Rules

```
OCR value         → Backend
──────────────────────────────
"paddleocr"       → PaddleOCR local (Arabic, RTL)
"azure_di_read"   → Azure DI Read API

Classifier value  → Backend
──────────────────────────────────────────
"local/arabert"   → HuggingFace AraBERT
"azure_di_classifier" → Azure DI Classifier
"litellm/<model>" → LiteLLM proxy (Gemini/Claude/Qwen)

Extractor value   → Backend
──────────────────────────────────────────
"local/layoutlmv3"    → HuggingFace LayoutLMv3
"azure_di_extractor"  → Azure DI Custom Extractor
"litellm/<model>"     → LiteLLM proxy
```

### Combo Switching (Hot Reload)

```
POST /api/combos/set  {"combo": "H1G"}
  → updates MAWRID_COMBO env var
  → calls settings.cache_clear()  ← Pydantic Settings lru_cache cleared
  → next request reads new combo immediately
  → no server restart required
```

---

## 6. Data Flow (End to End)

### Upload & Process

```
1. Client: POST /api/documents/upload  (multipart PDF)
   │
2. API: validate size (max 20 MB)
         create Job(status="pending", combo=active_combo)
         save to SQLite
         encode file as base64
         enqueue Celery task: process_document(job_id, file_b64, filename)
         return {job_id, status: "pending"}
   │
3. Worker: receive task
            decode base64 → file bytes
            call runner.run(file_bytes, filename, combo)
            run 5 pipeline stages (sequentially)
            log run to MLflow + SQLite (Run + FieldMetric records)
            update Job(status="completed", result=PipelineResult)
            store result in Redis
   │
4. Client: poll GET /api/documents/{job_id}
           or subscribe WS /ws/jobs/{job_id}
           receives full JobResponse with PipelineResult when done
```

### Review & Save

```
5. User reviews extracted fields in UI
   User edits any incorrect values
   User clicks Save
   │
6. POST /api/saved
   body: {doc_type, fields: [{field_id, value}, ...], ...}
   │
7. API: create SavedDocument record
         create SavedField records (1 per field)
         persist original file to disk: uploads/saved/{doc_id}/{filename}
         return saved document ID
```

---

## 7. API Reference

### Document Processing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/upload` | Upload file, enqueue pipeline, return job_id |
| `GET` | `/api/documents/{job_id}` | Poll job status and result |
| `WS` | `/ws/jobs/{job_id}` | Real-time stage-by-stage progress stream |

### Combo Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/combos` | List all combos and current active combo |
| `POST` | `/api/combos/set` | Switch active combo (no restart) |

### OCR Tools

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ocr/run` | Run PaddleOCR or EasyOCR standalone |
| `GET` | `/api/ocr/config` | PaddleOCR default config |
| `POST` | `/api/ocr/vision` | Claude vision OCR (direct Anthropic API) |
| `GET` | `/api/ocr/vision/models` | Available Claude vision models |

### Experiments

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/experiments` | Paginated list of MLflow runs |
| `POST` | `/api/experiments/compare` | Diff two runs side-by-side |

### Saved Documents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/saved` | Save reviewed document + fields |
| `GET` | `/api/saved` | List all saved documents |
| `GET` | `/api/saved/{doc_id}/file` | Download original uploaded file |
| `DELETE` | `/api/saved/{doc_id}` | Delete saved record |

### Utilities

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/schema` | Full schema (91 doc types + all field definitions) |
| `GET` | `/health` | Health check + active combo |

---

## 8. Database Schema

All MAWRID state is stored in SQLite (dev) or PostgreSQL (prod). MAWRID **never writes to Oracle** — Oracle is a read-only source for pulling training data only.

### Tables

#### `jobs` — Upload tracking
```
id              UUID        Primary key
filename        TEXT        Original filename
combo           TEXT        Active combo at upload time (e.g. "H1C")
status          TEXT        pending | running | completed | failed
created_at      DATETIME
completed_at    DATETIME    Null until done
error           TEXT        Error message if failed
```

#### `runs` — Completed pipeline executions
```
id                      UUID
job_id                  UUID → jobs.id
mlflow_run_id           TEXT    Cross-reference to MLflow
combo                   TEXT
doc_type                TEXT    Classified document type
num_fields              INT     Total fields in schema for this doc type
fields_matched          INT     Fields successfully extracted
confidence_avg          FLOAT   Average confidence across all fields
estimated_cost_usd      FLOAT   Estimated API cost for this run
latency_ms              INT     Total pipeline duration
azure_di_model_id       TEXT    Which Azure model was used (if any)
azure_pages_billed      INT
azure_confidence        FLOAT
```

#### `field_metrics` — Per-field results
```
id              INT (auto)
run_id          UUID → runs.id
field_id        TEXT        Schema field identifier
value           TEXT        Extracted value
confidence      FLOAT       0.0 – 1.0
low_confidence  BOOL        Flagged for human review
```

#### `saved_documents` — Human-verified records
```
id              UUID
filename        TEXT
file_path       TEXT        Path on disk
category        TEXT        e.g. "health_file"
category_label  TEXT        Arabic label
doc_type        TEXT
doc_type_label  TEXT        Arabic label
combo           TEXT
confidence      FLOAT
cost            FLOAT
latency         INT
created_at      DATETIME
→ saved_fields  (1-N)
```

#### `saved_fields` — Fields of a saved document
```
id              INT (auto)
document_id     UUID → saved_documents.id
field_id        TEXT
label_ar        TEXT        Arabic label from schema
value           TEXT        Final (possibly user-edited) value
confidence      FLOAT
```

---

## 9. Frontend Architecture

### Pages (5 routes)

| Path | Page | Purpose |
|------|------|---------|
| `/` | ProcessPage | Main workflow: upload → process → review fields → save |
| `/saved` | SavedRecordsPage | Browse and delete saved documents |
| `/experiments` | ExperimentsPage | View and compare MLflow pipeline runs |
| `/ocr` | OcrStagePage | Debug PaddleOCR configurations standalone |
| `/ocr-vision` | VisionOcrPage | Test Claude vision OCR |

### Component Tree

```
App (BrowserRouter + RTL/LTR toggle)
├── Sidebar (navigation, direction toggle)
└── Routes
    ├── ProcessPage
    │   ├── ComboSelector        (pick active combo)
    │   ├── DocumentUploader     (drag-drop file input)
    │   ├── PipelineStatus       (stage progress display)
    │   └── ResultViewer         (field list + confidence badges + edit)
    ├── SavedRecordsPage
    ├── ExperimentsPage
    │   └── ExperimentLog        (run comparison table)
    ├── OcrStagePage
    └── VisionOcrPage
```

### State Management

- **Server state:** React Query — handles polling, caching, invalidation automatically
- **UI state:** React `useState` — local component state
- **No global state manager** (Redux/Zustand) — React Query covers server-state needs

### Arabic / RTL Support

- `document.dir` toggled by user via Sidebar button
- All schema labels stored and rendered in Arabic
- Tailwind handles RTL layout with `dir="rtl"` on the root element

---

## 10. Infrastructure & Docker

### Services

| Service | Port | Description |
|---------|------|-------------|
| **redis** | 6380 (host) → 6379 | Celery broker + job result store |
| **backend** | 8000 | FastAPI app (hot reload via uvicorn --reload) |
| **worker** | — | Celery worker (ML-heavy, pre-caches PaddleOCR models) |
| **mlflow** | 5000 | Experiment tracking UI + REST API |
| **frontend** | 5173 | React dev server (Vite HMR, proxies /api and /ws to backend) |

### Split Requirements

The API and worker containers use different dependency sets deliberately:

```
requirements-api.txt      ← minimal (FastAPI, SQLAlchemy, Celery, Pydantic)
requirements-worker.txt   ← heavy (PaddleOCR, PyTorch, Transformers, EasyOCR)
requirements.txt          ← full (both merged, for local dev)
```

This keeps the API container lean and the ML container isolated — worker can be scaled independently.

### Volumes

- `paddleocr_models` — pre-cached PaddleOCR model weights (avoids re-download on restart)
- `mlflow_data` — MLflow tracking database and artifacts
- `./backend:/app` — hot-reload mount for both backend and worker

---

## 11. Document Schema

`config/schema_v2.json` is the single source of truth for all document definitions.

```json
{
  "_meta": {
    "version": "2.0",
    "doc_count": 91,
    "source": "Oracle DB"
  },
  "_categories": {
    "health_file": {"label_ar": "الملف الصحي"},
    "disciplinary": {"label_ar": "التأديبية"},
    ...
  },
  "documents": {
    "birth_certificate": {
      "label_ar": "شهادة الميلاد",
      "category": "personal_documents",
      "fields": [
        {"id": "name", "label_ar": "الاسم", "type": "text", "required": true},
        {"id": "dob",  "label_ar": "تاريخ الميلاد", "type": "date", "required": true},
        ...
      ]
    },
    ...
  }
}
```

**9 Categories, 91 Document Types:**
- `health_file` — الملف الصحي
- `employee_evaluation` — تقييم الموظف
- `academic_credentials` — المؤهلات الأكاديمية
- `cv` — السيرة الذاتية
- `disciplinary` — التأديبية
- `employment_procedures` — إجراءات التوظيف
- `correspondence` — المراسلات
- `personal_documents` — الوثائق الشخصية
- `admin_orders` — الأوامر الإدارية

The schema drives:
- **FormFill (Stage 4):** maps extracted keys to canonical field IDs
- **Validator (Stage 5):** checks required fields
- **Frontend ResultViewer:** renders correct Arabic labels and field types
- **SavedFields:** stores label_ar alongside value for offline readability

---

## 12. Experiment Tracking

Every completed pipeline run is logged to **two places simultaneously:**

### MLflow
- **Why:** Visual UI for comparing combos, filtering by metric, viewing artifacts
- Logs: `params` (combo, doc_type), `metrics` (fields_matched, confidence_avg, latency_ms, cost_usd)
- Accessible at `http://localhost:5000`

### SQLite (runs + field_metrics tables)
- **Why:** Queryable via FastAPI; the `/api/experiments` endpoint reads from here, not MLflow
- Lets the frontend show experiment data without a separate MLflow API call

### Metrics Tracked Per Run

| Metric | Description |
|--------|-------------|
| `combo` | Pipeline configuration used |
| `doc_type` | Classified document type |
| `num_fields` | Total fields expected by schema |
| `fields_matched` | Fields successfully extracted |
| `confidence_avg` | Average confidence across all fields (0.0–1.0) |
| `estimated_cost_usd` | Estimated API cost (LLM token pricing) |
| `latency_ms` | Total pipeline wall-clock time |
| `azure_pages_billed` | Azure DI billable pages (if applicable) |
| `azure_confidence` | Azure DI model confidence (if applicable) |

---

## 13. Key Design Decisions

### Why async FastAPI + Celery (not sync Django or sync FastAPI)?

OCR and LLM inference take 2–30 seconds per document. Blocking the API thread would kill throughput. The async API accepts requests instantly and returns a job ID; workers handle the heavy processing. The API scales horizontally (stateless), workers scale independently based on queue depth.

### Why the Combo Router pattern?

Without it, adding a new backend requires N×M code paths (3 stages × current backend count). With combos, each stage function receives a `route` dict and dispatches to the right backend in one place. Adding a new LLM backend means adding one entry in `combos.py` — no stage code changes.

### Why LiteLLM for cloud LLMs?

LiteLLM gives a single OpenAI-compatible interface to Gemini, Claude, Qwen, Ollama, and 100+ other providers. Switching from Claude to Gemini is one string change (`"litellm/claude-haiku-3"` → `"litellm/gemini/gemini-2.0-flash"`). No provider-specific SDK handling scattered across stages.

### Why PaddleOCR over Tesseract or EasyOCR?

PaddleOCR has significantly better Arabic OCR accuracy, especially for cursive handwritten document fonts. It also supports RTL text detection natively. It runs fully locally — no API cost, no data sent to cloud. EasyOCR is kept as a fallback.

### Why SQLite (dev) with PostgreSQL (prod)?

Zero-config development. One env var change (`DATABASE_URL`) switches the ORM engine. SQLAlchemy async supports both through `aiosqlite` and `asyncpg` drivers. No code changes required.

### Why split requirements files?

PaddleOCR + PyTorch + Transformers are ~3 GB of dependencies. The API container doesn't need them — it just dispatches tasks. Separate `requirements-api.txt` keeps the API image small and fast to build and deploy. Workers get the full ML stack.

### Why MLflow AND SQLite for experiments?

MLflow excels at visualization, run comparison, and artifact storage. But querying MLflow from a FastAPI endpoint requires the MLflow client library and adds latency. SQLite provides instant SQL queries for the experiments API endpoint. Both are written in the same Celery task for zero overhead.

### Why React Query instead of Redux or Zustand?

The only complex state in this app is server state (job status polling, saved document list, experiment runs). React Query handles polling intervals, background refetching, cache invalidation, and loading/error states automatically. Redux or Zustand would add boilerplate without benefit.

---

## 14. Current Status & Roadmap

### Build Order (Sequential)

| Step | Status | Description |
|------|--------|-------------|
| 1 | ✅ Done | Repo structure + Docker Compose |
| 2 | ✅ Done | Backend: settings + combo config |
| 3 | ✅ Done | Backend: pipeline runner with mocked stages |
| 4 | ✅ Done | Backend: all API endpoints against mocked pipeline |
| 5 | ✅ Done | Frontend: full UI connected to mock backend |
| 6 | 🔄 Next | Backend: replace mocks with real PaddleOCR + LiteLLM |
| 7 | ⏳ Pending | MLflow logging (full metrics integration) |

### Currently Stubbed (Step 6 targets)

- **Classifier** — always returns `"birth_certificate"`; replace with AraBERT or LLM dispatch
- **Extractor** — always returns 8 hardcoded fields; replace with LayoutLMv3 or LLM dispatch
- **Azure DI backends** — SDK integrated but not called end-to-end
- **Local model backends** — HuggingFace infrastructure in place but models not loaded

### Working Now

- OCR: PaddleOCR local + Azure DI Read
- Vision OCR: Claude via Anthropic SDK (H1C combo)
- FormFill: deterministic Python schema mapper
- Validator: confidence heuristic scoring
- Full frontend UI (upload, review, save, experiments, debug tools)
- Celery async pipeline dispatch
- WebSocket real-time updates
- Combo hot-switching
- MLflow + SQLite experiment logging (structure in place)

---

*Last updated: 2026-05-10*
