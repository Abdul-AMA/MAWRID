"""
Saved-document CRUD, shared by /api/saved (main.py) and /api/mawrid/saved
(routers/mawrid.py). Pure DB + filesystem logic — no FastAPI dependencies,
so both routers can wrap it with their own request/response shapes.
"""

from __future__ import annotations
import json
import uuid
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SavedDocument, SavedField

UPLOADS_DIR = Path(__file__).parent.parent / "uploads" / "saved"


def saved_doc_to_dict(doc: SavedDocument) -> dict:
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


async def create_document(
    db: AsyncSession,
    *,
    filename: str,
    file_bytes: bytes,
    category: str,
    category_label: str,
    doc_type: str,
    doc_type_label: str,
    combo: str = "",
    confidence: float = 0.0,
    cost: float = 0.0,
    latency: float = 0.0,
    fields_json: str = "[]",
) -> dict:
    doc_id = str(uuid.uuid4())

    dest_dir = UPLOADS_DIR / doc_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename or "document").name
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
    return saved_doc_to_dict(result.scalar_one())


async def list_documents(db: AsyncSession, limit: int = 100, offset: int = 0) -> dict:
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
    return {"records": [saved_doc_to_dict(r) for r in rows], "total": total}


async def get_document(db: AsyncSession, doc_id: str) -> SavedDocument | None:
    return await db.get(SavedDocument, doc_id)


async def delete_document(db: AsyncSession, doc_id: str) -> bool:
    doc = await db.get(SavedDocument, doc_id)
    if not doc:
        return False
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
    return True
