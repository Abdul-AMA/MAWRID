"""
Laravel-compatible alias router — mirrors ~/coding/laravel-api-mawrid's
routes/api.php + MawridController.php exactly (same paths, same request
shapes), so the API Dog collection documented in that repo's apidog.txt
works against this backend by swapping only the base URL.

Extras beyond the Laravel API (additive, ignored by the Laravel-shaped
client): page_images/input_tokens/output_tokens/prompt on stage responses,
schema_token support, and the working /saved endpoints (Laravel's are
declared in routes but the controller methods were never implemented).
"""

from __future__ import annotations
import base64
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from database.engine import get_db
from models.schemas import DEFAULT_BACKEND, Stage2Request, Stage3Request
from pipeline.orchestrator import (
    api_key_for, load_schema, run_pipeline, run_stage1, run_stage2, run_stage3,
    StageError,
)
from pipeline.vision_stage1 import to_pages
import services.saved_documents as saved_documents

router = APIRouter(prefix="/api/mawrid", tags=["mawrid"])


# ── Health / schema ──────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/schema")
async def schema():
    return load_schema()


# ── Pipeline ──────────────────────────────────────────────────────────────────

@router.post("/pipeline/run")
async def pipeline_run(
    file: UploadFile = File(...),
    stage1_backend: str = Form(default=DEFAULT_BACKEND),
    stage2_backend: str = Form(default=""),
    stage3_backend: str = Form(default=""),
    document_type: str = Form(default=""),
    prompt_lang: str = Form(default="ar"),
    schema_token: str = Form(default=""),
):
    settings = get_settings()
    file_bytes = await file.read()

    try:
        return await run_pipeline(
            file_bytes,
            stage1_backend,
            stage2_backend or stage1_backend,
            stage3_backend or stage1_backend,
            prompt_lang,
            settings,
            schema_token,
            document_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except StageError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/pipeline/stage1")
async def pipeline_stage1(
    file: UploadFile = File(...),
    stage1_backend: str = Form(default=DEFAULT_BACKEND),
    prompt_lang: str = Form(default="ar"),
):
    settings = get_settings()
    key = api_key_for(stage1_backend, settings)
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key for {stage1_backend.split('/')[0]}")

    file_bytes = await file.read()
    try:
        return await run_stage1(file_bytes, stage1_backend, key, prompt_lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stage 1 failed: {exc}")


@router.post("/pipeline/stage2")
async def pipeline_stage2(body: Stage2Request):
    settings = get_settings()
    key = api_key_for(body.stage2_backend, settings)
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key for {body.stage2_backend.split('/')[0]}")

    try:
        return await run_stage2(body.raw_text, body.stage2_backend, key, body.prompt_lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stage 2 failed: {exc}")


@router.post("/pipeline/stage3")
async def pipeline_stage3(body: Stage3Request):
    settings = get_settings()
    key = api_key_for(body.stage3_backend, settings)
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key for {body.stage3_backend.split('/')[0]}")

    try:
        return await run_stage3(body.raw_text, body.document_type, body.stage3_backend, key, body.prompt_lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stage 3 failed: {exc}")


# ── Saved documents ───────────────────────────────────────────────────────────

@router.post("/saved", status_code=201)
async def saved_create(
    file: UploadFile = File(...),
    category: str = Form(...),
    category_label: str = Form(...),
    doc_type: str = Form(...),
    doc_type_label: str = Form(...),
    combo: str = Form(default=""),
    confidence: float = Form(default=0.0),
    cost: float = Form(default=0.0),
    latency: float = Form(default=0.0),
    fields_json: str = Form(default="[]"),
    db: AsyncSession = Depends(get_db),
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


@router.get("/saved")
async def saved_list(db: AsyncSession = Depends(get_db), limit: int = 100, offset: int = 0):
    return await saved_documents.list_documents(db, limit, offset)


@router.get("/saved/{doc_id}/file")
async def saved_download(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await saved_documents.get_document(db, doc_id)
    if not doc or not doc.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    fp = Path(doc.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(fp), filename=doc.filename)


@router.delete("/saved/{doc_id}", status_code=204)
async def saved_delete(doc_id: str, db: AsyncSession = Depends(get_db)):
    if not await saved_documents.delete_document(db, doc_id):
        raise HTTPException(status_code=404, detail="Record not found")


# ── Dev: PDF/image preprocessing test (no LLM call) ─────────────────────────

@router.post("/test/pdf-processor")
async def test_pdf_processor(file: UploadFile = File(...)):
    file_bytes = await file.read()
    pages = to_pages(file_bytes)
    b64_pages = [base64.b64encode(p).decode() for p in pages]
    return {
        "pages_count": len(pages),
        "pages": [
            {"page": i + 1, "size_kb": round(len(b64) * 3 / 4 / 1024, 1)}
            for i, b64 in enumerate(b64_pages)
        ],
        "first_page": b64_pages[0] if b64_pages else None,
    }
