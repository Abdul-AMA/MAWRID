"""
Stage 2 — Document Classification.

Backends:
  local/arabert[-finetuned]  → HuggingFace AraBERT  [Step 6]
  azure_di_classifier        → Azure DI Custom Classifier  [Step 6]
  litellm/<model>            → Cloud LLM via LiteLLM  [Step 6]

Currently returns stub classification.
"""

from __future__ import annotations

STUB_DOC_TYPE = "birth_certificate"


async def run(text: str, backend: str, route: dict) -> str:
    """Return predicted document type string."""
    # TODO Step 6: dispatch to real backend
    if backend.startswith("local/"):
        return _stub_local(text)
    if backend == "azure_di_classifier":
        return _stub_azure(text)
    if backend.startswith("litellm/"):
        return await _stub_litellm(text, backend)
    raise ValueError(f"Unknown classifier backend: {backend}")


def _stub_local(text: str) -> str:
    return STUB_DOC_TYPE


def _stub_azure(text: str) -> str:
    return STUB_DOC_TYPE


async def _stub_litellm(text: str, backend: str) -> str:
    return STUB_DOC_TYPE
