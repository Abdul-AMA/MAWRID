"""
Experiment tracker — writes to both MLflow and SQLite on every pipeline run.

Called by the Celery worker after each completed pipeline run.
"""

from __future__ import annotations
import mlflow
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Run, FieldMetric
from models.schemas import PipelineResult
from config.settings import get_settings


async def log_run(
    job_id: str,
    result: PipelineResult,
    db: AsyncSession,
) -> str:
    """
    Log a completed pipeline run to MLflow + SQLite.
    Returns the MLflow run_id.
    """
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("mawrid-pipeline")

    num_fields = len(result.fields)
    fields_matched = sum(1 for f in result.fields if f.value is not None)

    # ── MLflow ────────────────────────────────────────────────────────────────
    with mlflow.start_run() as mlrun:
        mlflow.log_params({
            "combo": result.combo,
            "doc_type": result.doc_type,
        })
        mlflow.log_metrics({
            "num_fields":         num_fields,
            "fields_matched":     fields_matched,
            "confidence_avg":     result.confidence_avg,
            "estimated_cost_usd": result.estimated_cost_usd,
            "latency_ms":         result.total_latency_ms,
        })
        mlflow_run_id = mlrun.info.run_id

    # ── SQLite ────────────────────────────────────────────────────────────────
    run = Run(
        job_id=job_id,
        mlflow_run_id=mlflow_run_id,
        combo=result.combo,
        doc_type=result.doc_type,
        num_fields=num_fields,
        fields_matched=fields_matched,
        confidence_avg=result.confidence_avg,
        estimated_cost_usd=result.estimated_cost_usd,
        latency_ms=result.total_latency_ms,
    )
    db.add(run)
    await db.flush()  # get run.id before adding metrics

    for f in result.fields:
        db.add(FieldMetric(
            run_id=run.id,
            field_id=f.field_id,
            value=f.value,
            confidence=f.confidence,
            low_confidence=f.low_confidence,
        ))

    await db.commit()
    return mlflow_run_id
