"""
Shared pipeline orchestration used by both the legacy /api/two-stage/* routes
(main.py) and the Laravel-compatible /api/mawrid/* routes (routers/mawrid.py).

Kept provider-agnostic: this module only sequences the three stages and
handles schema lookups. Provider dispatch stays in vision_stage1.py /
text_stage2.py.
"""

from __future__ import annotations
import asyncio
import json
import uuid
from pathlib import Path

from pipeline.vision_stage1 import run_sync as _s1_run
from pipeline.text_stage2 import classify_sync as _s2_classify, run_sync as _s3_run

_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "schema_v2.json"
_schema_cache: dict | None = None

# In-memory store for user-uploaded schemas keyed by token
_custom_schemas: dict[str, dict] = {}


def api_key_for(backend: str, settings) -> str:
    if backend.startswith("openrouter/"):
        return settings.openrouter_api_key
    if backend.startswith("gemini/"):
        return settings.gemini_api_key
    if backend.startswith("groq/"):
        return settings.groq_api_key
    if backend.startswith("claude/"):
        return settings.anthropic_api_key
    if backend.startswith("ollama/"):
        return settings.ollama_base_url
    if backend.startswith("openai/"):
        # Real OpenAI API (text stages only — see text_stage2._call_openai).
        # Not to be confused with Groq's "openai/gpt-oss-120b" model id,
        # which is dispatched via the groq/ prefix.
        return settings.openai_api_key
    return ""


def load_schema(token: str = "") -> dict:
    if token:
        schema = _custom_schemas.get(token)
        if not schema:
            raise KeyError(token)
        return schema

    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


def register_schema(schema: dict) -> str:
    token = str(uuid.uuid4())
    _custom_schemas[token] = schema
    return token


def _enrich_stage2(s2: dict, schema_token: str = "") -> dict:
    """Attach document_type_label, category, category_label, field_count from the schema."""
    active_schema = _custom_schemas.get(schema_token) if schema_token else None
    if active_schema is None:
        active_schema = load_schema()

    doc_type = s2["document_type"]
    doc_def = active_schema.get("documents", {}).get(doc_type, {})
    s2["document_type_label"] = doc_def.get("label_ar", doc_type)
    s2["category"] = doc_def.get("category", "")
    s2["category_label"] = doc_def.get("category_label_ar", "")
    s2["field_count"] = len(doc_def.get("fields", []))
    return s2


async def run_stage1(file_bytes: bytes, backend: str, api_key: str, lang: str = "ar") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _s1_run(file_bytes, backend, api_key, lang))


async def run_stage2(raw_text: str, backend: str, api_key: str, lang: str = "ar", schema_token: str = "") -> dict:
    loop = asyncio.get_event_loop()
    s2 = await loop.run_in_executor(None, lambda: _s2_classify(raw_text, backend, api_key, lang))
    return _enrich_stage2(s2, schema_token)


async def run_stage3(raw_text: str, doc_type: str, backend: str, api_key: str, lang: str = "ar") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _s3_run(raw_text, doc_type, backend, api_key, lang))


class StageError(Exception):
    def __init__(self, stage: int, exc: Exception):
        self.stage = stage
        self.exc = exc
        super().__init__(f"Stage {stage} failed: {exc}")


async def run_pipeline(
    file_bytes: bytes,
    stage1_backend: str,
    stage2_backend: str,
    stage3_backend: str,
    lang: str,
    settings,
    schema_token: str = "",
    document_type: str = "",
) -> dict:
    """
    Full 3-stage pipeline. Raises StageError(stage, exc) on failure so callers
    can map it to their own HTTP error shape. Raises ValueError if stage1 has
    no API key.

    If `document_type` is supplied, stage 2 is skipped and stage 3 runs
    directly against that doc type (mirrors the Laravel API's `document_type`
    form field, used to skip re-classification).
    """
    key1 = api_key_for(stage1_backend, settings)
    key2 = api_key_for(stage2_backend, settings)
    key3 = api_key_for(stage3_backend, settings)

    if not key1:
        raise ValueError(f"No API key for {stage1_backend.split('/')[0]}")

    try:
        s1 = await run_stage1(file_bytes, stage1_backend, key1, lang)
    except Exception as exc:
        raise StageError(1, exc) from exc

    if document_type:
        s2: dict = _enrich_stage2(
            {"document_type": document_type, "confidence": "high",
             "model": stage2_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0},
            schema_token,
        )
    else:
        s2 = _enrich_stage2(
            {"document_type": "غير_محدد", "confidence": "low",
             "model": stage2_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0},
            schema_token,
        )
        if key2 and s1.get("raw_text"):
            try:
                s2 = await run_stage2(s1["raw_text"], stage2_backend, key2, lang, schema_token)
            except Exception as exc:
                raise StageError(2, exc) from exc

    doc_type = s2["document_type"]
    s3: dict = {"fields": {}, "model": stage3_backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
    if key3 and doc_type != "غير_محدد":
        try:
            s3 = await run_stage3(s1["raw_text"], doc_type, stage3_backend, key3, lang)
        except Exception as exc:
            raise StageError(3, exc) from exc

    return {"stage1": s1, "stage2": s2, "stage3": s3}
