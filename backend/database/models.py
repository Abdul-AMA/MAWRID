from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class SavedDocument(Base):
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
    __tablename__ = "saved_fields"

    id: Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str]  = mapped_column(String(36), ForeignKey("saved_documents.id"), nullable=False)
    field_id: Mapped[str]     = mapped_column(String(64),  nullable=False)
    label_ar: Mapped[str]     = mapped_column(String(128), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    document: Mapped[SavedDocument] = relationship("SavedDocument", back_populates="fields")
