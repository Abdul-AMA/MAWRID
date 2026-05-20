"""
Combo routing table.

Each combo maps to the runner interface:
  ocr:        "paddleocr" | "azure_di_read"
  classifier: "local/arabert" | "azure_di_classifier" | "litellm/<model>"
  extractor:  "local/layoutlmv3" | "azure_di_extractor" | "litellm/<model>"
"""

from typing import TypedDict, Literal

OcrBackend = Literal["paddleocr", "azure_di_read"]
LocalBackend = Literal["local/arabert", "local/layoutlmv3"]
AzureBackend = Literal["azure_di_classifier", "azure_di_extractor"]
LiteLLMBackend = str  # "litellm/<model-id>"


class ComboRoute(TypedDict):
    ocr: str
    classifier: str
    extractor: str
    description: str
    sends_images_to_cloud: bool


COMBO_MAP: dict[str, ComboRoute] = {
    # ── Pure Local ──────────────────────────────────────────────────────────
    "L1": {
        "ocr": "paddleocr",
        "classifier": "local/arabert",
        "extractor": "local/layoutlmv3",
        "description": "Pretrained local — PaddleOCR + AraBERT zero-shot + LayoutLMv3 zero-shot",
        "sends_images_to_cloud": False,
    },
    "L3": {
        "ocr": "paddleocr",
        "classifier": "local/arabert-finetuned",
        "extractor": "local/layoutlmv3-finetuned",
        "description": "Fully trained local — PaddleOCR + AraBERT fine-tuned + LayoutLMv3 fine-tuned",
        "sends_images_to_cloud": False,
    },
    # ── Pure Cloud: Azure ────────────────────────────────────────────────────
    "AZ": {
        "ocr": "azure_di_read",
        "classifier": "azure_di_classifier",
        "extractor": "azure_di_extractor",
        "description": "Pure Azure Document Intelligence",
        "sends_images_to_cloud": True,
    },
    # ── Pure Cloud: Frontier LLM ────────────────────────────────────────────
    "FL": {
        "ocr": "vision",  # images sent directly to Gemini — OCR skipped
        "classifier": "litellm/gemini/gemini-2.0-flash",
        "extractor": "litellm/gemini/gemini-2.0-flash",
        "description": "Pure frontier vision — Gemini 2.0 Flash handles OCR+classify+extract in one call",
        "sends_images_to_cloud": True,  # ⚠ raw page images sent to cloud
    },
    # ── Hybrid: Local OCR + Cloud LLM ───────────────────────────────────────
    "H1G": {
        "ocr": "paddleocr",
        "classifier": "litellm/gemini/gemini-2.0-flash",
        "extractor": "litellm/gemini/gemini-2.0-flash",
        "description": "Hybrid Gemini — PaddleOCR + Gemini 2.0 Flash classify + extract",
        "sends_images_to_cloud": False,
    },
    "H1C": {
        "ocr": "paddleocr",
        "classifier": "litellm/anthropic/claude-haiku-4-5-20251001",
        "extractor": "litellm/anthropic/claude-haiku-4-5-20251001",
        "description": "Hybrid Claude — PaddleOCR + Claude Haiku classify + extract",
        "sends_images_to_cloud": False,
    },
    "H1Q": {
        "ocr": "paddleocr",
        "classifier": "litellm/qwen/qwen-max",
        "extractor": "litellm/qwen/qwen-max",
        "description": "Hybrid Qwen — PaddleOCR + Qwen-Max classify + extract",
        "sends_images_to_cloud": False,
    },
    # ── Hybrid: Local OCR + Azure ────────────────────────────────────────────
    "H1A": {
        "ocr": "paddleocr",
        "classifier": "azure_di_classifier",
        "extractor": "azure_di_extractor",
        "description": "Hybrid Azure — local OCR (best data residency), Azure DI classify + extract",
        "sends_images_to_cloud": False,  # only text sent to Azure
    },
    # ── Hybrid: Best local + cheapest cloud ─────────────────────────────────
    "H2": {
        "ocr": "paddleocr",
        "classifier": "local/arabert-finetuned",
        "extractor": "litellm/gemini/gemini-2.0-flash",
        "description": "Smart hybrid — AraBERT fine-tuned classify, Gemini extract only",
        "sends_images_to_cloud": False,
    },
    # ── Hybrid: Local + Azure fallback ──────────────────────────────────────
    "H3": {
        "ocr": "paddleocr",
        "classifier": "local/arabert-finetuned",
        "extractor": "azure_di_extractor",
        "description": "Azure fallback — AraBERT fine-tuned classify, Azure DI extract only",
        "sends_images_to_cloud": False,
    },
}

VALID_COMBOS = list(COMBO_MAP.keys())


def get_combo(name: str) -> ComboRoute:
    if name not in COMBO_MAP:
        raise ValueError(f"Unknown combo '{name}'. Valid: {VALID_COMBOS}")
    return COMBO_MAP[name]
