<div align="center">

# مَوْرِد · MAWRID

**AI-Powered Arabic Document Processing System**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Groq](https://img.shields.io/badge/Groq-Powered-F55036?logoColor=white)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)

</div>

---

## What is MAWRID?

MAWRID is an end-to-end system that takes Arabic document images or PDFs and turns them into structured, searchable data — automatically.

You upload a document. MAWRID reads it, figures out what type it is, and pulls out all the relevant fields as clean JSON. The result is ready to store, query, or feed into any downstream system.

```
Arabic PDF / Image
        │
        ▼
   Stage 1 — OCR          Extract raw text from the document
        │
        ▼
   Stage 2 — Classify     Identify the document type
        │
        ▼
   Stage 3 — Extract      Pull out all structured fields
        │
        ▼
   Stage 4 — FormFill     Map fields to a canonical schema
        │
        ▼
   Stage 5 — Validate     Score confidence, flag uncertain fields
        │
        ▼
     Structured JSON
```

The pipeline is modular — each stage runs independently, so you can swap backends, benchmark them, and measure exactly where quality is gained or lost.

---

## Key Features

- **Arabic-first** — full RTL support throughout the UI, schema, and output
- **Multi-page PDF support** — automatically splits pages and processes each one
- **Async processing** — upload returns immediately; results stream back via WebSocket
- **Live experiments dashboard** — every run is logged with metrics so you can compare models side by side
- **Human review loop** — extracted fields are shown in a review UI before saving; users can correct any value
- **LLM-powered** — uses Groq's fast inference for classification and extraction; local OCR keeps costs low

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                     │
│   Upload → Process → Review → Save  │  Experiments      │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                    BACKEND (FastAPI)                      │
│   Receive upload → queue job → stream progress back      │
└──────────────────────┬──────────────────────────────────┘
                       │ async task dispatch
┌──────────────────────▼──────────────────────────────────┐
│                    WORKER (Celery)                        │
│   OCR  →  Classify (Groq)  →  Extract (Groq)            │
│   FormFill  →  Validate                                  │
└──────┬─────────────────┬────────────────┬───────────────┘
       │                 │                │
  ┌────▼────┐     ┌──────▼─────┐   ┌─────▼──────┐
  │  Redis  │     │  Database  │   │   MLflow   │
  │(broker) │     │  (results) │   │ (tracking) │
  └─────────┘     └────────────┘   └────────────┘
```

---

## Tech Stack

**Backend** — Python 3.11, FastAPI, Celery + Redis, PaddleOCR, PyMuPDF, SQLAlchemy, MLflow

**Frontend** — React 18, TypeScript, Vite, Tailwind CSS, React Query

**AI** — Groq API for fast LLM inference (classification + extraction), PaddleOCR for local OCR

**Infrastructure** — Docker Compose, SQLite (dev) / PostgreSQL (prod), WebSocket for real-time updates

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- A [Groq API key](https://console.groq.com)

### Run

```bash
git clone https://github.com/Abood-AMA/MAWRID.git
cd MAWRID
cp .env.example .env
# Add your GROQ_API_KEY to .env
docker compose up
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API docs | http://localhost:8000/docs |
| MLflow experiments | http://localhost:5000 |

### Environment Variables

```env
GROQ_API_KEY=gsk_...
DATABASE_URL=sqlite+aiosqlite:///./mawrid.db   # swap to postgres for prod
```

---

## API Reference

```
POST /api/documents/upload     Upload a document and start the pipeline
GET  /api/documents/{job_id}   Poll for job status and result
WS   /ws/jobs/{job_id}         Stream real-time stage-by-stage progress

GET  /api/experiments          View all pipeline runs with metrics
POST /api/experiments/compare  Compare two runs side by side

POST /api/ocr/run              Run OCR standalone (debug)
GET  /api/schema               The full document type schema
GET  /health                   Health check
```

---

## Frontend

| Route | Purpose |
|-------|---------|
| `/` | Upload a document, watch it process, review and save the result |
| `/saved` | Browse all saved documents |
| `/experiments` | View and compare pipeline runs across different models |
| `/ocr` | Test and debug OCR output directly |

---

## Why "MAWRID"?

**مَوْرِد** (mawrid) means *a source* or *a resource* in Arabic — a place you go to get what you need. Documents go in; structured data comes out.

---
