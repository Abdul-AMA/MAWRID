"""
SQLAlchemy ORM models for MAWRID's internal storage.

tables:
  jobs    — one row per uploaded document / pipeline run request
  runs    — one row per completed pipeline run (metrics, logged to MLflow too)
  metrics — one row per extracted field in a run
"""

from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str]         = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str]   = mapped_column(String(255), nullable=False)
    combo: Mapped[str]      = mapped_column(String(16), nullable=False)
    status: Mapped[str]     = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None]     = mapped_column(Text, nullable=True)

    run: Mapped[Run | None] = relationship("Run", back_populates="job", uselist=False)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str]       = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    combo: Mapped[str]        = mapped_column(String(16), nullable=False)
    doc_type: Mapped[str]     = mapped_column(String(64), nullable=False)
    num_fields: Mapped[int]   = mapped_column(Integer, nullable=False)
    fields_matched: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_avg: Mapped[float]      = mapped_column(Float, nullable=False)
    estimated_cost_usd: Mapped[float]  = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float]          = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    # Azure-specific (null for non-Azure combos)
    azure_di_model_id: Mapped[str | None]    = mapped_column(String(128), nullable=True)
    azure_pages_billed: Mapped[int | None]   = mapped_column(Integer, nullable=True)
    azure_confidence: Mapped[float | None]   = mapped_column(Float, nullable=True)

    job: Mapped[Job]              = relationship("Job", back_populates="run")
    field_metrics: Mapped[list[FieldMetric]] = relationship("FieldMetric", back_populates="run")


class FieldMetric(Base):
    __tablename__ = "metrics"

    id: Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str]    = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    field_id: Mapped[str]  = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float]    = mapped_column(Float, nullable=False)
    low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    run: Mapped[Run] = relationship("Run", back_populates="field_metrics")


# ── Saved documents (user-confirmed records) ──────────────────────────────────

class SavedDocument(Base):
    """One row per document the user explicitly saved after reviewing fields."""
    __tablename__ = "saved_documents"

    id: Mapped[str]               = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str]         = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str]         = mapped_column(String(64),  nullable=False)
    category_label: Mapped[str]   = mapped_column(String(128), nullable=False)
    doc_type: Mapped[str]         = mapped_column(String(64),  nullable=False)
    doc_type_label: Mapped[str]   = mapped_column(String(128), nullable=False)
    combo: Mapped[str]            = mapped_column(String(64),  nullable=False, default="")
    confidence: Mapped[float]     = mapped_column(Float,   nullable=False, default=0.0)
    cost: Mapped[float]           = mapped_column(Float,   nullable=False, default=0.0)
    latency: Mapped[float]        = mapped_column(Float,   nullable=False, default=0.0)
    created_at: Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)

    fields: Mapped[list[SavedField]] = relationship(
        "SavedField", back_populates="document", cascade="all, delete-orphan"
    )


class SavedField(Base):
    """One row per field value inside a SavedDocument."""
    __tablename__ = "saved_fields"

    id: Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str]  = mapped_column(String(36), ForeignKey("saved_documents.id"), nullable=False)
    field_id: Mapped[str]     = mapped_column(String(64),  nullable=False)
    label_ar: Mapped[str]     = mapped_column(String(128), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    document: Mapped[SavedDocument] = relationship("SavedDocument", back_populates="fields")
