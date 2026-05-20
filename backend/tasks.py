"""
Celery tasks for async pipeline execution.
"""

from __future__ import annotations
import asyncio
from celery_app import celery_app
from database.engine import get_session_factory, init_db


@celery_app.task(name="tasks.run_ocr_only")
def run_ocr_only(file_b64: str, backend: str, params: dict | None = None) -> dict:
    """Run only Stage 1 (OCR) — returns layout data with bboxes and page images."""
    import base64, time
    from pipeline.ocr import run_layout, _stub_azure

    file_bytes = base64.b64decode(file_b64)
    t0 = time.monotonic()

    if backend in ("paddleocr", "easyocr"):
        pages = run_layout(file_bytes, backend, params)
        text  = "\n".join(d["text"] for p in pages for d in p["detections"])
    elif backend == "azure_di_read":
        text, pages = _stub_azure(file_bytes), []
    else:
        text, pages = "", []

    return {
        "text":       text,
        "backend":    backend,
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        "pages":      pages,
    }


@celery_app.task(bind=True, name="tasks.process_document")
def process_document(self, job_id: str, file_bytes_b64: str, filename: str):
    """
    Execute the full pipeline for a document.
    Runs in a Celery worker (sync wrapper around async pipeline).
    """
    async def _fail(exc):
        factory = get_session_factory()
        async with factory() as db:
            from database.models import Job
            from datetime import datetime
            job = await db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = datetime.utcnow()
                await db.commit()

    try:
        import base64
        from pipeline import runner
        from database.models import Job
        from datetime import datetime

        file_bytes = base64.b64decode(file_bytes_b64)

        async def _run():
            await init_db()
            factory = get_session_factory()

            async with factory() as db:
                job = await db.get(Job, job_id)
                if job:
                    job.status = "running"
                    await db.commit()

            result = await runner.run(file_bytes, filename)

            async with factory() as db:
                from experiments.tracker import log_run
                mlflow_run_id = await log_run(job_id, result, db)

                job = await db.get(Job, job_id)
                if job:
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    if job.run:
                        job.run.mlflow_run_id = mlflow_run_id
                    await db.commit()

            return result.model_dump()

        return asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_fail(exc))
        raise
