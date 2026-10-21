"""Pydantic request bodies for the JSON-based /api/mawrid/* routes."""

from __future__ import annotations
from pydantic import BaseModel

DEFAULT_BACKEND = "groq/meta-llama/llama-4-scout-17b-16e-instruct"


class Stage2Request(BaseModel):
    raw_text: str
    stage2_backend: str = DEFAULT_BACKEND
    prompt_lang: str = "ar"


class Stage3Request(BaseModel):
    raw_text: str
    document_type: str
    stage3_backend: str = DEFAULT_BACKEND
    prompt_lang: str = "ar"
