from __future__ import annotations
import base64
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket,
    WebSocketDisconnect
)
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from config.combos import COMBO_MAP, get_combo
from database.engine import get_db, init_db
from database.models import Job, Run, FieldMetric, SavedDocument, SavedField
from models.schemas import (
    UploadResponse, JobResponse, JobStatus,
    ComboListResponse, ComboInfo, ComboSetRequest, ComboSetResponse,
    ExperimentsResponse, ExperimentRun, CompareRequest, CompareResponse,
    StageStatus,
)


async def _poll_celery(task, timeout: int = 600) -> dict:
    """Poll a Celery result without holding a Redis pub/sub connection open."""
    import asyncio, time
    deadline = time.monotonic() + timeout
    while True:
        state = task.state
        if state == "SUCCESS":
            return task.result
        if state == "FAILURE":
            raise RuntimeError(str(task.result))
        if time.monotonic() > deadline:
            raise TimeoutError(f"OCR task timed out after {timeout}s")
        await asyncio.sleep(2)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = Annotated[AsyncSession, Depends(get_db)]


# ── Documents ─────────────────────────────────────────────────────────────────

@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    job_id = str(uuid.uuid4())
    job = Job(id=job_id, filename=file.filename or "upload", combo=settings.mawrid_combo)
    db.add(job)
    await db.commit()

    # Enqueue Celery task
    from tasks import process_document
    process_document.delay(job_id, base64.b64encode(file_bytes).decode(), file.filename)

    return UploadResponse(job_id=job_id)


@app.get("/api/documents/{job_id}", response_model=JobResponse)
async def get_document_status(job_id: str, db: DB):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = None
    if job.run and job.status == "completed":
        # Reconstruct PipelineResult from DB
        from models.schemas import PipelineResult, StageResult, ExtractedField
        metrics = (
            await db.execute(
                select(FieldMetric).where(FieldMetric.run_id == job.run.id)
            )
        ).scalars().all()
        result = PipelineResult(
            doc_type=job.run.doc_type,
            combo=job.run.combo,
            stages=[],  # stage detail not persisted yet — added in Step 4
            fields=[
                ExtractedField(
                    field_id=m.field_id,
                    value=m.value,
                    confidence=m.confidence,
                    low_confidence=m.low_confidence,
                )
                for m in metrics
            ],
            confidence_avg=job.run.confidence_avg,
            estimated_cost_usd=job.run.estimated_cost_usd,
            total_latency_ms=job.run.latency_ms,
            mlflow_run_id=job.run.mlflow_run_id,
        )

    return JobResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        combo=job.combo,
        filename=job.filename,
        result=result,
        error=job.error,
    )


# ── Combos ────────────────────────────────────────────────────────────────────

@app.get("/api/combos", response_model=ComboListResponse)
async def list_combos():
    settings = get_settings()
    active = settings.mawrid_combo
    combos = [
        ComboInfo(
            name=name,
            description=c["description"],
            ocr=c["ocr"],
            classifier=c["classifier"],
            extractor=c["extractor"],
            sends_images_to_cloud=c["sends_images_to_cloud"],
            active=(name == active),
        )
        for name, c in COMBO_MAP.items()
    ]
    return ComboListResponse(combos=combos, active=active)


@app.post("/api/combos/set", response_model=ComboSetResponse)
async def set_combo(body: ComboSetRequest):
    try:
        get_combo(body.combo)  # validates the name
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    import os
    os.environ["MAWRID_COMBO"] = body.combo
    # Bust the settings cache so next request picks up the new combo
    get_settings.cache_clear()

    return ComboSetResponse(active=body.combo, message=f"Active combo set to {body.combo}")


# ── OCR Stage ─────────────────────────────────────────────────────────────────

@app.post("/api/ocr/run")
async def run_ocr_stage(
    file: UploadFile = File(...),
    backend: str = Form(default=""),
    params_json: str = Form(default=""),
):
    import base64, json
    from tasks import run_ocr_only

    if not backend:
        combo   = get_combo(get_settings().mawrid_combo)
        backend = combo["ocr"]
    if backend == "vision":
        backend = "paddleocr"

    params = json.loads(params_json) if params_json else None

    file_bytes = await file.read()
    task       = run_ocr_only.delay(base64.b64encode(file_bytes).decode(), backend, params)

    result = await _poll_celery(task, timeout=600)
    return result


@app.get("/api/ocr/config")
async def get_ocr_config():
    from pipeline.ocr import PADDLE_CONFIG
    return {"paddleocr": PADDLE_CONFIG}


@app.post("/api/ocr/vision")
async def run_ocr_vision(
    file: UploadFile = File(...),
    model: str = Form(default="claude-sonnet-4-6"),
    prompt: str = Form(default=""),
):
    import asyncio
    from pipeline.vision import run_vision_ocr, DEFAULT_PROMPT

    settings = get_settings()
    if not settings.anthropic_api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY is not configured")

    file_bytes = await file.read()
    used_prompt = prompt.strip() or DEFAULT_PROMPT

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_vision_ocr(file_bytes, model, used_prompt, settings.anthropic_api_key),
        )
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@app.get("/api/ocr/vision/models")
async def list_vision_models():
    from pipeline.vision import CLAUDE_MODELS
    return {"models": CLAUDE_MODELS}


# ── Gemini Vision OCR ─────────────────────────────────────────────────────────

@app.post("/api/ocr/gemini")
async def run_ocr_gemini(
    file: UploadFile = File(...),
    model: str = Form(default="gemini-2.0-flash"),
    prompt: str = Form(default=""),
):
    import asyncio
    from pipeline.gemini_vision import run_gemini_ocr, DEFAULT_PROMPT as GEMINI_DEFAULT_PROMPT

    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY is not configured")

    file_bytes = await file.read()
    used_prompt = prompt.strip() or GEMINI_DEFAULT_PROMPT

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_gemini_ocr(file_bytes, model, used_prompt, settings.gemini_api_key),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@app.get("/api/ocr/gemini/models")
async def list_gemini_models():
    from pipeline.gemini_vision import GEMINI_MODELS
    return {"models": GEMINI_MODELS}


# ── Azure Document Intelligence OCR ──────────────────────────────────────────

@app.post("/api/ocr/azure")
async def run_ocr_azure(
    file: UploadFile = File(...),
    model: str = Form(default="prebuilt-read"),
):
    import asyncio
    from pipeline.azure_di import run_azure_di_ocr

    settings = get_settings()
    if not settings.azure_di_endpoint or not settings.azure_di_key:
        raise HTTPException(status_code=400, detail="AZURE_DI_ENDPOINT and AZURE_DI_KEY are not configured")

    file_bytes = await file.read()

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_azure_di_ocr(file_bytes, model, settings.azure_di_endpoint, settings.azure_di_key),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@app.get("/api/ocr/azure/models")
async def list_azure_models():
    from pipeline.azure_di import AZURE_DI_MODELS
    return {"models": AZURE_DI_MODELS}


# ── Groq Vision OCR ──────────────────────────────────────────────────────────

@app.post("/api/ocr/groq")
async def run_ocr_groq(
    file: UploadFile = File(...),
    model: str = Form(default="meta-llama/llama-4-scout-17b-16e-instruct"),
    prompt: str = Form(default=""),
):
    import asyncio
    from pipeline.groq_vision import run_groq_ocr, DEFAULT_PROMPT as GROQ_PROMPT

    settings = get_settings()
    if not settings.groq_api_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY is not configured")

    file_bytes = await file.read()
    used_prompt = prompt.strip() or GROQ_PROMPT

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_groq_ocr(file_bytes, model, used_prompt, settings.groq_api_key),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@app.get("/api/ocr/groq/models")
async def list_groq_models():
    from pipeline.groq_vision import GROQ_MODELS
    return {"models": GROQ_MODELS}


# ── OpenRouter Vision OCR ─────────────────────────────────────────────────────

@app.post("/api/ocr/openrouter")
async def run_ocr_openrouter(
    file: UploadFile = File(...),
    model: str = Form(default="meta-llama/llama-4-scout:free"),
    prompt: str = Form(default=""),
):
    import asyncio
    from pipeline.openrouter_vision import run_openrouter_ocr, DEFAULT_PROMPT as OR_PROMPT

    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY is not configured")

    file_bytes = await file.read()
    used_prompt = prompt.strip() or OR_PROMPT

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_openrouter_ocr(file_bytes, model, used_prompt, settings.openrouter_api_key),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@app.get("/api/ocr/openrouter/models")
async def list_openrouter_models():
    from pipeline.openrouter_vision import OPENROUTER_MODELS
    return {"models": OPENROUTER_MODELS}


# ── Two-Stage Pipeline ───────────────────────────────────────────────────────

GROQ_SCOUT    = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
CLAUDE_SONNET = "claude/claude-sonnet-4-6"
OLLAMA_VL     = "ollama/qwen2.5vl:3b"
OLLAMA_TEXT   = "ollama/qwen2.5:3b"

STAGE1_MODELS = [GROQ_SCOUT, CLAUDE_SONNET, OLLAMA_VL]
STAGE2_MODELS = [GROQ_SCOUT, CLAUDE_SONNET, OLLAMA_VL, OLLAMA_TEXT]
STAGE3_MODELS = [GROQ_SCOUT, CLAUDE_SONNET, OLLAMA_VL, OLLAMA_TEXT]


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
        return settings.ollama_base_url  # no API key — pass base URL instead
    if backend.startswith("openai/"):
        return settings.anthropic_api_key
    return ""


@app.get("/api/two-stage/models")
async def list_two_stage_models():
    return {"stage1": STAGE1_MODELS, "stage2": STAGE2_MODELS, "stage3": STAGE3_MODELS}


@app.post("/api/two-stage/run")
async def run_two_stage(
    file: UploadFile = File(...),
    stage1_backend: str = Form(default=GROQ_SCOUT),
    stage2_backend: str = Form(default=GROQ_SCOUT),
    stage3_backend: str = Form(default=GROQ_SCOUT),
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

    # ── Stage 1: vision OCR ──────────────────────────────────────────────────
    try:
        s1 = await loop.run_in_executor(None, lambda: s1_run(file_bytes, stage1_backend, key1))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stage 1 failed: {exc}")

    # ── Stage 2: classify doc type from raw text ─────────────────────────────
    s2: dict = {"document_type": "غير_محدد", "confidence": "low",
                "model": stage2_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
    if key2 and s1.get("raw_text"):
        try:
            s2 = await loop.run_in_executor(
                None, lambda: classify_sync(s1["raw_text"], stage2_backend, key2)
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stage 2 failed: {exc}")

    # Enrich stage2 with schema metadata
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    doc_type = s2["document_type"]
    doc_def  = _schema_cache.get("documents", {}).get(doc_type, {})
    s2["document_type_label"] = doc_def.get("label_ar", doc_type)
    s2["field_count"]         = len(doc_def.get("fields", []))

    # ── Stage 3: extract fields from raw text ────────────────────────────────
    s3: dict = {"fields": {}, "model": stage3_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
    if key3 and doc_type != "غير_محدد":
        try:
            s3 = await loop.run_in_executor(
                None, lambda: s3_run(s1["raw_text"], doc_type, stage3_backend, key3)
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stage 3 failed: {exc}")

    return {"stage1": s1, "stage2": s2, "stage3": s3}


# ── Experiments ───────────────────────────────────────────────────────────────

@app.get("/api/experiments", response_model=ExperimentsResponse)
async def list_experiments(db: DB, limit: int = 100, offset: int = 0):
    total = (await db.execute(select(func.count()).select_from(Run))).scalar_one()
    rows = (
        await db.execute(
            select(Run).order_by(Run.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    runs = [_run_to_schema(r) for r in rows]
    return ExperimentsResponse(runs=runs, total=total)


@app.post("/api/experiments/compare", response_model=CompareResponse)
async def compare_experiments(body: CompareRequest, db: DB):
    run_a = await db.get(Run, body.run_id_a)
    run_b = await db.get(Run, body.run_id_b)
    if not run_a or not run_b:
        raise HTTPException(status_code=404, detail="One or both run IDs not found")

    sa, sb = _run_to_schema(run_a), _run_to_schema(run_b)
    delta = {
        "confidence_avg":     round(sb.confidence_avg - sa.confidence_avg, 4),
        "estimated_cost_usd": round(sb.estimated_cost_usd - sa.estimated_cost_usd, 6),
        "latency_ms":         round(sb.latency_ms - sa.latency_ms, 1),
        "fields_matched":     sb.fields_matched - sa.fields_matched,
        "precision":          round(sb.precision - sa.precision, 4),
        "recall":             round(sb.recall - sa.recall, 4),
    }
    return CompareResponse(run_a=sa, run_b=sb, delta=delta)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    """
    Stream pipeline stage updates to the client.
    Polls job status and pushes updates. In Step 4 this will use Redis pub/sub.
    """
    import asyncio
    await websocket.accept()
    try:
        prev_status = None
        while True:
            async for db in get_db():
                job = await db.get(Job, job_id)
                if not job:
                    await websocket.send_json({"type": "error", "error": "Job not found"})
                    return

                if job.status != prev_status:
                    prev_status = job.status
                    await websocket.send_json({"type": "status_update", "status": job.status})

                if job.status in ("completed", "failed"):
                    await websocket.send_json({"type": job.status})
                    return

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# ── Saved documents ──────────────────────────────────────────────────────────

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

    # Persist file to disk
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

    # Re-fetch with fields eager-loaded
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
    # Remove file from disk
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


# ── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA_PATH = Path(__file__).parent / "config" / "schema_v2.json"
_schema_cache: dict | None = None


@app.get("/api/schema")
async def get_schema():
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "combo": get_settings().mawrid_combo}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_to_schema(r: Run) -> ExperimentRun:
    precision = r.fields_matched / r.num_fields if r.num_fields else 0.0
    recall = precision  # stub: treat precision == recall until ground truth exists
    return ExperimentRun(
        run_id=r.id,
        combo=r.combo,
        doc_type=r.doc_type,
        num_fields=r.num_fields,
        fields_matched=r.fields_matched,
        precision=precision,
        recall=recall,
        confidence_avg=r.confidence_avg,
        estimated_cost_usd=r.estimated_cost_usd,
        latency_ms=r.latency_ms,
        timestamp=r.created_at.isoformat(),
        azure_di_model_id=r.azure_di_model_id,
        azure_pages_billed=r.azure_pages_billed,
        azure_confidence=r.azure_confidence,
    )
