from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ── Job / pipeline ────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class StageStatus(str, Enum):
    WAITING   = "waiting"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"


class StageResult(BaseModel):
    name: str
    status: StageStatus = StageStatus.WAITING
    latency_ms: float | None = None
    output_summary: str | None = None


class ExtractedField(BaseModel):
    field_id: str
    value: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool = False


class PipelineResult(BaseModel):
    doc_type: str
    combo: str
    stages: list[StageResult]
    fields: list[ExtractedField]
    confidence_avg: float
    estimated_cost_usd: float
    total_latency_ms: float
    mlflow_run_id: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    combo: str
    filename: str
    result: PipelineResult | None = None
    error: str | None = None


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    message: str = "Document queued for processing"


# ── Combo ─────────────────────────────────────────────────────────────────────

class ComboInfo(BaseModel):
    name: str
    description: str
    ocr: str
    classifier: str
    extractor: str
    sends_images_to_cloud: bool
    active: bool


class ComboListResponse(BaseModel):
    combos: list[ComboInfo]
    active: str


class ComboSetRequest(BaseModel):
    combo: str


class ComboSetResponse(BaseModel):
    active: str
    message: str


# ── Experiments ───────────────────────────────────────────────────────────────

class ExperimentRun(BaseModel):
    run_id: str
    combo: str
    doc_type: str
    num_fields: int
    fields_matched: int
    precision: float
    recall: float
    confidence_avg: float
    estimated_cost_usd: float
    latency_ms: float
    timestamp: str
    # Azure-specific (null for non-Azure combos)
    azure_di_model_id: str | None = None
    azure_pages_billed: int | None = None
    azure_confidence: float | None = None


class ExperimentsResponse(BaseModel):
    runs: list[ExperimentRun]
    total: int


class CompareRequest(BaseModel):
    run_id_a: str
    run_id_b: str


class CompareResponse(BaseModel):
    run_a: ExperimentRun
    run_b: ExperimentRun
    delta: dict[str, Any]


# ── WebSocket ─────────────────────────────────────────────────────────────────

class WsMessage(BaseModel):
    type: str  # "stage_update" | "completed" | "error"
    stage: str | None = None
    status: StageStatus | None = None
    latency_ms: float | None = None
    result: PipelineResult | None = None
    error: str | None = None
