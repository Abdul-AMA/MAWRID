from __future__ import annotations
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Annotated, Optional

from config.settings import get_settings
from database.engine import get_db, init_db
from routers.mawrid import router as mawrid_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="MAWRID API",
    description="AI document processing system — Municipality of Gaza",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()
_origins = ["http://localhost:5173", "http://localhost:3000"]
if _settings.allowed_origins:
    _origins += [o.strip() for o in _settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mawrid_router)

DB = Annotated[AsyncSession, Depends(get_db)]


# ── Laravel-shaped error envelope, scoped to /api/mawrid/* only ────────────────
# Mirrors MawridController::handle() in laravel-api-mawrid: validation errors
# -> {"error": "validation_failed", "message", "errors"} at 422, everything
# else -> {"error": "server_error", "message"} at its original status code.
# Routes outside /api/mawrid/* keep FastAPI's default {"detail": ...} shape.

@app.exception_handler(RequestValidationError)
async def _mawrid_validation_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/api/mawrid/"):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    return JSONResponse(
        status_code=422,
        content={"error": "validation_failed", "message": str(exc), "errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def _mawrid_http_exception_handler(request: Request, exc: HTTPException):
    if not request.url.path.startswith("/api/mawrid/"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
    if exc.status_code == 422:
        return JSONResponse(status_code=422, content={"error": "validation_failed", "message": exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"error": "server_error", "message": exc.detail})


# ── Schema ────────────────────────────────────────────────────────────────────

from pipeline.orchestrator import (
    load_schema, register_schema, run_pipeline, StageError,
)


@app.get("/api/schema")
async def get_schema(token: Optional[str] = None):
    try:
        return load_schema(token or "")
    except KeyError:
        raise HTTPException(status_code=404, detail="Schema token not found or expired")


@app.post("/api/schema/upload")
async def upload_schema(file: UploadFile = File(...)):
    """Accept a custom JSON schema file and return a token to use it."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    raw = await file.read()
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}")

    if "documents" not in schema:
        raise HTTPException(status_code=422, detail="Schema must have a 'documents' key")

    token = register_schema(schema)
    return {"token": token, "doc_count": len(schema.get("documents", {}))}


# ── Two-Stage Pipeline ────────────────────────────────────────────────────────

GROQ_SCOUT    = "groq/openai/gpt-oss-120b"
CLAUDE_SONNET = "claude/claude-sonnet-4-6"
OLLAMA_VL     = "ollama/qwen2.5vl:3b"
OLLAMA_TEXT   = "ollama/qwen2.5:3b"


@app.post("/api/two-stage/run")
async def run_two_stage(
    file: UploadFile = File(...),
    stage1_backend: str = Form(default=GROQ_SCOUT),
    stage2_backend: str = Form(default=GROQ_SCOUT),
    stage3_backend: str = Form(default=GROQ_SCOUT),
    prompt_lang: str = Form(default="ar"),
    schema_token: str = Form(default=""),
):
    settings = get_settings()
    file_bytes = await file.read()

    try:
        return await run_pipeline(
            file_bytes, stage1_backend, stage2_backend, stage3_backend,
            prompt_lang, settings, schema_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except StageError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Saved documents ───────────────────────────────────────────────────────────

import services.saved_documents as saved_documents


@app.post("/api/saved")
async def create_saved_document(
    file: UploadFile = File(...),
    category: str       = Form(...),
    category_label: str = Form(...),
    doc_type: str       = Form(...),
    doc_type_label: str = Form(...),
    combo: str          = Form(default=""),
    confidence: float   = Form(default=0.0),
    cost: float         = Form(default=0.0),
    latency: float      = Form(default=0.0),
    fields_json: str    = Form(default="[]"),
    db: AsyncSession    = Depends(get_db),
):
    file_bytes = await file.read()
    return await saved_documents.create_document(
        db,
        filename=file.filename or "document",
        file_bytes=file_bytes,
        category=category,
        category_label=category_label,
        doc_type=doc_type,
        doc_type_label=doc_type_label,
        combo=combo,
        confidence=confidence,
        cost=cost,
        latency=latency,
        fields_json=fields_json,
    )


@app.get("/api/saved")
async def list_saved_documents(db: DB, limit: int = 100, offset: int = 0):
    return await saved_documents.list_documents(db, limit, offset)


@app.get("/api/saved/{doc_id}/file")
async def get_saved_file(doc_id: str, db: DB):
    doc = await saved_documents.get_document(db, doc_id)
    if not doc or not doc.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    fp = Path(doc.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(fp), filename=doc.filename)


@app.delete("/api/saved/{doc_id}", status_code=204)
async def delete_saved_document(doc_id: str, db: DB):
    if not await saved_documents.delete_document(db, doc_id):
        raise HTTPException(status_code=404, detail="Record not found")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
