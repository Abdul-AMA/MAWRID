from __future__ import annotations
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Annotated, Optional

from config.settings import get_settings
from database.engine import get_db, init_db
from database.models import SavedDocument, SavedField


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

DB = Annotated[AsyncSession, Depends(get_db)]


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_PATH = Path(__file__).parent / "config" / "schema_v2.json"
_schema_cache: dict | None = None

# In-memory store for user-uploaded schemas keyed by token
_custom_schemas: dict[str, dict] = {}


@app.get("/api/schema")
async def get_schema(token: Optional[str] = None):
    if token:
        schema = _custom_schemas.get(token)
        if not schema:
            raise HTTPException(status_code=404, detail="Schema token not found or expired")
        return schema

    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


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

    token = str(uuid.uuid4())
    _custom_schemas[token] = schema
    return {"token": token, "doc_count": len(schema.get("documents", {}))}


# ── Two-Stage Pipeline ────────────────────────────────────────────────────────

GROQ_SCOUT    = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
CLAUDE_SONNET = "claude/claude-sonnet-4-6"
OLLAMA_VL     = "ollama/qwen2.5vl:3b"
OLLAMA_TEXT   = "ollama/qwen2.5:3b"


def _api_key_for(backend: str, settings) -> str:
    if backend.startswith("openrouter/"):
        return settings.openrouter_api_key
    if backend.startswith("gemini/"):
        return settings.gemini_api_key
    if backend.startswith("groq/"):
        return settings.groq_api_key
    if backend.startswith("claude/"):
        return settings.anthropic_api_key
    if backend.startswith("ollama/"):
        return settings.ollama_base_url
    if backend.startswith("openai/"):
        return settings.anthropic_api_key
    return ""


@app.post("/api/two-stage/run")
async def run_two_stage(
    file: UploadFile = File(...),
    stage1_backend: str = Form(default=GROQ_SCOUT),
    stage2_backend: str = Form(default=GROQ_SCOUT),
    stage3_backend: str = Form(default=GROQ_SCOUT),
    prompt_lang: str = Form(default="ar"),
    schema_token: str = Form(default=""),
):
    import asyncio
    from pipeline.vision_stage1 import run_sync as s1_run
    from pipeline.text_stage2 import classify_sync, run_sync as s3_run

    settings = get_settings()
    key1 = _api_key_for(stage1_backend, settings)
    key2 = _api_key_for(stage2_backend, settings)
    key3 = _api_key_for(stage3_backend, settings)

    if not key1:
        raise HTTPException(status_code=400, detail=f"No API key for {stage1_backend.split('/')[0]}")

    file_bytes = await file.read()
    loop = asyncio.get_event_loop()

    try:
        s1 = await loop.run_in_executor(None, lambda: s1_run(file_bytes, stage1_backend, key1, prompt_lang))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stage 1 failed: {exc}")

    s2: dict = {"document_type": "غير_محدد", "confidence": "low",
                "model": stage2_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
    if key2 and s1.get("raw_text"):
        try:
            s2 = await loop.run_in_executor(
                None, lambda: classify_sync(s1["raw_text"], stage2_backend, key2, prompt_lang)
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stage 2 failed: {exc}")

    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    active_schema = _custom_schemas.get(schema_token) if schema_token else None
    if active_schema is None:
        active_schema = _schema_cache

    doc_type = s2["document_type"]
    doc_def  = active_schema.get("documents", {}).get(doc_type, {})
    s2["document_type_label"] = doc_def.get("label_ar", doc_type)
    s2["field_count"]         = len(doc_def.get("fields", []))

    s3: dict = {"fields": {}, "model": stage3_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
    if key3 and doc_type != "غير_محدد":
        try:
            s3 = await loop.run_in_executor(
                None, lambda: s3_run(s1["raw_text"], doc_type, stage3_backend, key3, prompt_lang)
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stage 3 failed: {exc}")

    return {"stage1": s1, "stage2": s2, "stage3": s3}


# ── Saved documents ───────────────────────────────────────────────────────────

_UPLOADS_DIR = Path(__file__).parent / "uploads" / "saved"


def _saved_doc_to_dict(doc: SavedDocument) -> dict:
    return {
        "id":             doc.id,
        "filename":       doc.filename,
        "category":       doc.category,
        "category_label": doc.category_label,
        "doc_type":       doc.doc_type,
        "doc_type_label": doc.doc_type_label,
        "combo":          doc.combo,
        "confidence":     doc.confidence,
        "cost":           doc.cost,
        "latency":        doc.latency,
        "created_at":     doc.created_at.isoformat(),
        "fields": [
            {
                "field_id":   f.field_id,
                "label_ar":   f.label_ar,
                "value":      f.value,
                "confidence": f.confidence,
            }
            for f in doc.fields
        ],
    }


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
    doc_id     = str(uuid.uuid4())
    file_bytes = await file.read()

    dest_dir = _UPLOADS_DIR / doc_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "document").name
    file_path = dest_dir / safe_name
    file_path.write_bytes(file_bytes)

    fields_data: list[dict] = json.loads(fields_json)

    doc = SavedDocument(
        id=doc_id,
        filename=safe_name,
        file_path=str(file_path),
        category=category,
        category_label=category_label,
        doc_type=doc_type,
        doc_type_label=doc_type_label,
        combo=combo,
        confidence=confidence,
        cost=cost,
        latency=latency,
    )
    db.add(doc)

    for f in fields_data:
        db.add(SavedField(
            document_id=doc_id,
            field_id=f["field_id"],
            label_ar=f["label_ar"],
            value=f.get("value") or None,
            confidence=float(f.get("confidence", 0.0)),
        ))

    await db.commit()

    result = await db.execute(
        select(SavedDocument)
        .where(SavedDocument.id == doc_id)
        .options(selectinload(SavedDocument.fields))
    )
    doc = result.scalar_one()
    return _saved_doc_to_dict(doc)


@app.get("/api/saved")
async def list_saved_documents(db: DB, limit: int = 100, offset: int = 0):
    total = (
        await db.execute(select(func.count()).select_from(SavedDocument))
    ).scalar_one()
    rows = (
        await db.execute(
            select(SavedDocument)
            .options(selectinload(SavedDocument.fields))
            .order_by(SavedDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {"records": [_saved_doc_to_dict(r) for r in rows], "total": total}


@app.get("/api/saved/{doc_id}/file")
async def get_saved_file(doc_id: str, db: DB):
    doc = await db.get(SavedDocument, doc_id)
    if not doc or not doc.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    fp = Path(doc.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(fp), filename=doc.filename)


@app.delete("/api/saved/{doc_id}", status_code=204)
async def delete_saved_document(doc_id: str, db: DB):
    doc = await db.get(SavedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    if doc.file_path:
        fp = Path(doc.file_path)
        if fp.exists():
            fp.unlink()
        if fp.parent.exists():
            try:
                fp.parent.rmdir()
            except OSError:
                pass
    await db.delete(doc)
    await db.commit()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
