"""
Combo orchestrator.

Reads the active combo from settings and routes each stage to the correct
backend implementation. All stages are stubbed and return mock data until
Step 6 (real implementations).
"""

from __future__ import annotations
import time
from config.settings import get_settings
from config.combos import get_combo
from models.schemas import (
    PipelineResult, StageResult, StageStatus, ExtractedField
)
from pipeline import ocr, classifier, extractor, formfill, validator


async def run(file_bytes: bytes, filename: str) -> PipelineResult:
    settings = get_settings()
    combo_name = settings.mawrid_combo
    route = get_combo(combo_name)

    stages: list[StageResult] = []
    total_start = time.monotonic()

    # Stage 1 — OCR
    s1 = await _run_stage("ocr", lambda: ocr.run(file_bytes, route["ocr"]))
    stages.append(s1)

    raw_text: str = s1.output_summary or ""

    # Stage 2 — Classification
    s2 = await _run_stage(
        "classifier",
        lambda: classifier.run(raw_text, route["classifier"], route)
    )
    stages.append(s2)

    doc_type: str = s2.output_summary or "unknown"

    # Stage 3 — Extraction
    s3 = await _run_stage(
        "extractor",
        lambda: extractor.run(raw_text, doc_type, route["extractor"], route)
    )
    stages.append(s3)

    # Stage 4 — Form fill (deterministic)
    s4_start = time.monotonic()
    raw_fields = formfill.fill(doc_type, s3.output_summary or "{}")
    s4 = StageResult(
        name="formfill",
        status=StageStatus.DONE,
        latency_ms=(time.monotonic() - s4_start) * 1000,
    )
    stages.append(s4)

    # Stage 5 — Validation
    s5_start = time.monotonic()
    validated_fields = validator.validate(raw_fields)
    s5 = StageResult(
        name="validator",
        status=StageStatus.DONE,
        latency_ms=(time.monotonic() - s5_start) * 1000,
    )
    stages.append(s5)

    total_ms = (time.monotonic() - total_start) * 1000
    confidence_avg = (
        sum(f.confidence for f in validated_fields) / len(validated_fields)
        if validated_fields else 0.0
    )

    return PipelineResult(
        doc_type=doc_type,
        combo=combo_name,
        stages=stages,
        fields=validated_fields,
        confidence_avg=confidence_avg,
        estimated_cost_usd=0.0,
        total_latency_ms=total_ms,
    )


async def _run_stage(name: str, fn) -> StageResult:
    start = time.monotonic()
    try:
        output = await fn() if _is_coroutine(fn) else fn()
        return StageResult(
            name=name,
            status=StageStatus.DONE,
            latency_ms=(time.monotonic() - start) * 1000,
            output_summary=str(output) if output is not None else None,
        )
    except Exception as exc:
        return StageResult(
            name=name,
            status=StageStatus.FAILED,
            latency_ms=(time.monotonic() - start) * 1000,
            output_summary=str(exc),
        )


def _is_coroutine(fn) -> bool:
    import asyncio, inspect
    return inspect.iscoroutinefunction(fn)
