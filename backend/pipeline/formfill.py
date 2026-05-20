"""
Stage 4 — Form Fill (deterministic).

Maps raw extractor output (dict) onto the canonical form schema for the
detected document type. Returns a list of {field_id, value} dicts.
No AI involved — pure Python mapping.
"""

from __future__ import annotations
import json
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "form_schemas.json"
_schemas: dict | None = None


def _get_schemas() -> dict:
    global _schemas
    if _schemas is None:
        _schemas = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schemas


def fill(doc_type: str, extracted_json: str) -> list[dict]:
    """
    Map extracted fields onto the form schema.
    Returns [{"field_id": str, "value": str | None}, ...].
    """
    schemas = _get_schemas()
    schema = schemas.get(doc_type)
    if schema is None:
        return []

    try:
        extracted: dict = json.loads(extracted_json)
    except (json.JSONDecodeError, TypeError):
        extracted = {}

    return [
        {
            "field_id": field["id"],
            "value": extracted.get(field["id"]),
        }
        for field in schema["fields"]
    ]
