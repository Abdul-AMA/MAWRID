"""
Quick manual test for the two-stage pipeline.

Usage:
    python scripts/test_two_stage.py path/to/document.jpg

Set env vars before running:
    export OPENROUTER_API_KEY=sk-or-...
"""

import sys
import asyncio
import json
import os
from pathlib import Path

# Allow running from the backend/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.vision_stage1 import run as stage1
from pipeline.text_stage2 import run as stage2


STAGE1_BACKEND = "openrouter/google/gemma-3-27b-it:free"
STAGE2_BACKEND = "openrouter/google/gemma-3-27b-it:free"


async def main(image_path: str):
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: set OPENROUTER_API_KEY env var")
        sys.exit(1)

    file_bytes = Path(image_path).read_bytes()

    # ── Stage 1: vision model → classify + OCR ──────────────────────────────
    print("Stage 1: classifying + extracting text...")
    s1 = await stage1(file_bytes, STAGE1_BACKEND, api_key)

    print(f"  document_type : {s1['document_type']}")
    print(f"  confidence    : {s1['confidence']}")
    print(f"  tokens in/out : {s1['input_tokens']} / {s1['output_tokens']}")
    print(f"  latency       : {s1['latency_ms']} ms")
    print(f"  raw_text[:200]: {s1['raw_text'][:200]!r}")
    print()

    # ── Stage 2: text model → extract fields ────────────────────────────────
    print("Stage 2: extracting fields from text...")
    s2 = await stage2(s1["raw_text"], s1["document_type"], STAGE2_BACKEND, api_key)

    print(f"  tokens in/out : {s2['input_tokens']} / {s2['output_tokens']}")
    print(f"  latency       : {s2['latency_ms']} ms")
    print()
    print("Extracted fields:")
    print(json.dumps(s2["fields"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_two_stage.py <image_or_pdf_path>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
