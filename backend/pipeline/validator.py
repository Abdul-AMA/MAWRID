"""
Stage 5 — Validation.

Assigns a confidence score to each field and flags low-confidence ones
for human review. Stub uses heuristic confidence based on value presence.
Real implementation will use model-returned confidence scores.
"""

from __future__ import annotations
from models.schemas import ExtractedField

LOW_CONFIDENCE_THRESHOLD = 0.6
STUB_CONFIDENCE_PRESENT = 0.88
STUB_CONFIDENCE_MISSING = 0.0


def validate(raw_fields: list[dict]) -> list[ExtractedField]:
    """
    Input: list of {field_id, value} from formfill.
    Output: list of ExtractedField with confidence + low_confidence flag.
    """
    result = []
    for f in raw_fields:
        value = f.get("value")
        # Stub: confidence based on whether a value was found
        confidence = STUB_CONFIDENCE_PRESENT if value else STUB_CONFIDENCE_MISSING
        result.append(ExtractedField(
            field_id=f["field_id"],
            value=value,
            confidence=confidence,
            low_confidence=confidence < LOW_CONFIDENCE_THRESHOLD,
        ))
    return result
