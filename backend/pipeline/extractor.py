"""
Stage 3 — Field Extraction.

Backends:
  local/layoutlmv3[-finetuned] → HuggingFace LayoutLMv3  [Step 6]
  azure_di_extractor           → Azure DI Custom Extractor  [Step 6]
  litellm/<model>              → Cloud LLM via LiteLLM  [Step 6]

Currently returns stub extracted fields as a JSON string.
"""

from __future__ import annotations
import json

STUB_FIELDS = {
    "full_name":          "محمد أحمد السيد",
    "date_of_birth":      "1990-05-15",
    "place_of_birth":     "غزة",
    "father_name":        "أحمد محمود السيد",
    "mother_name":        "فاطمة عبد الله",
    "gender":             "ذكر",
    "registration_number":"123456789",
    "issue_date":         "2023-01-01",
    "issuing_authority":  "وزارة الداخلية",
}


async def run(text: str, doc_type: str, backend: str, route: dict) -> str:
    """Return extracted fields as a JSON string."""
    # TODO Step 6: dispatch to real backend
    if backend.startswith("local/"):
        return _stub_local(text, doc_type)
    if backend == "azure_di_extractor":
        return _stub_azure(text, doc_type)
    if backend.startswith("litellm/"):
        return await _stub_litellm(text, doc_type, backend)
    raise ValueError(f"Unknown extractor backend: {backend}")


def _stub_local(text: str, doc_type: str) -> str:
    return json.dumps(STUB_FIELDS, ensure_ascii=False)


def _stub_azure(text: str, doc_type: str) -> str:
    return json.dumps(STUB_FIELDS, ensure_ascii=False)


async def _stub_litellm(text: str, doc_type: str, backend: str) -> str:
    return json.dumps(STUB_FIELDS, ensure_ascii=False)
