"""
Stage 1 — Vision OCR only.

Single job: extract all visible text from the document image.
Does NOT classify. Classification is Stage 2 (text-only model).

Supported backends:
  openrouter/<model>   — any OpenRouter vision model
  gemini/<model>       — Google Gemini
  groq/<model>         — Groq vision model (e.g. llama-4-scout)
"""

from __future__ import annotations
import json
import re
import base64
import io
import time
from pathlib import Path

from pipeline.prompts import build_stage1_prompt


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_sync(file_bytes: bytes, backend: str, api_key: str) -> dict:
    """
    Synchronous OCR-only stage. Returns raw_text + page_images.
    Returns:
        { raw_text, page_images, model, latency_ms, input_tokens, output_tokens }
    """
    jpeg_pages = _to_jpeg_pages(file_bytes)
    prompt     = build_stage1_prompt()
    raw        = _dispatch(jpeg_pages, prompt, backend, api_key)
    raw_text   = _parse_ocr_response(raw["text"])
    page_images = [base64.b64encode(p).decode() for p in jpeg_pages]
    return {**raw, "raw_text": raw_text, "page_images": page_images}


async def run(file_bytes: bytes, backend: str, api_key: str) -> dict:
    """Async wrapper for the test script."""
    return run_sync(file_bytes, backend, api_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dispatch(pages: list[bytes], prompt: str, backend: str, api_key: str) -> dict:
    if backend.startswith("openrouter/"):
        return _call_openrouter(pages, prompt, backend[len("openrouter/"):], api_key)
    if backend.startswith("gemini/"):
        return _call_gemini(pages, prompt, backend[len("gemini/"):], api_key)
    if backend.startswith("groq/"):
        return _call_groq(pages, prompt, backend[len("groq/"):], api_key)
    if backend.startswith("claude/"):
        return _call_claude(pages, prompt, backend[len("claude/"):], api_key)
    if backend.startswith("ollama/"):
        return _call_ollama(pages, prompt, backend[len("ollama/"):], api_key)
    raise ValueError(f"Unsupported vision_stage1 backend: {backend}")


def _parse_ocr_response(text: str) -> str:
    """Extract raw_text from model JSON response. Falls back to full text."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
        return data.get("raw_text", text)
    except json.JSONDecodeError:
        match = re.search(r'"raw_text"\s*:\s*"(.*?)"(?=\s*[,}])', cleaned, re.DOTALL)
        if match:
            return match.group(1).replace("\\n", "\n")
        return text  # model returned plain text instead of JSON — use it directly


# ---------------------------------------------------------------------------
# (kept for backwards compat — previously extracted doc_type too)
# ---------------------------------------------------------------------------

def _parse_response(text: str) -> dict:
    return {
        "raw_text": _parse_ocr_response(text),
    }


# ---------------------------------------------------------------------------
# Image preprocessing — convert any input to JPEG page(s)
# ---------------------------------------------------------------------------

_MAX_WIDTH = 600


def _to_jpeg_pages(file_bytes: bytes) -> list[bytes]:
    from PIL import Image as PILImage, ImageEnhance

    def _preprocess(img):
        gray = img.convert("L")
        if gray.width > _MAX_WIDTH:
            ratio = _MAX_WIDTH / gray.width
            gray = gray.resize((_MAX_WIDTH, int(gray.height * ratio)), PILImage.LANCZOS)
        return ImageEnhance.Contrast(gray).enhance(1.5)

    if file_bytes[:4] == b"%PDF":
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            _preprocess(img).save(buf, format="JPEG", quality=85, optimize=True)
            pages.append(buf.getvalue())
        doc.close()
        return pages

    buf = io.BytesIO()
    img = PILImage.open(io.BytesIO(file_bytes))
    _preprocess(img).save(buf, format="JPEG", quality=85, optimize=True)
    return [buf.getvalue()]


def _pages_to_b64(pages: list[bytes]) -> list[str]:
    return [base64.b64encode(p).decode() for p in pages]


# ---------------------------------------------------------------------------
# Backend: OpenRouter (OpenAI-compatible)
# ---------------------------------------------------------------------------

def _call_openrouter(pages: list[bytes], prompt: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"X-Title": "MAWRID"},
    )

    content: list = []
    for idx, page_bytes in enumerate(pages):
        b64 = base64.b64encode(page_bytes).decode()
        if len(pages) > 1:
            content.append({"type": "text", "text": f"الصفحة {idx + 1}:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=8192,
    )
    usage = resp.usage

    return {
        "text":          resp.choices[0].message.content or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }


# ---------------------------------------------------------------------------
# Backend: Google Gemini
# ---------------------------------------------------------------------------

def _call_gemini(pages: list[bytes], prompt: str, model: str, api_key: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts: list = []
    for idx, page_bytes in enumerate(pages):
        if len(pages) > 1:
            parts.append(f"الصفحة {idx + 1}:")
        parts.append(types.Part.from_bytes(data=page_bytes, mime_type="image/jpeg"))
    parts.append(prompt)

    t0 = time.monotonic()
    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(max_output_tokens=8192),
    )

    usage = resp.usage_metadata
    return {
        "text":          resp.text or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.prompt_token_count or 0,
        "output_tokens": usage.candidates_token_count or 0,
    }


# ---------------------------------------------------------------------------
# Backend: Groq
# ---------------------------------------------------------------------------

def _call_groq(pages: list[bytes], prompt: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)

    content: list = []
    for idx, page_bytes in enumerate(pages):
        b64 = base64.b64encode(page_bytes).decode()
        if len(pages) > 1:
            content.append({"type": "text", "text": f"الصفحة {idx + 1}:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=8192,
    )
    usage = resp.usage

    return {
        "text":          resp.choices[0].message.content or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }


# ---------------------------------------------------------------------------
# Backend: Anthropic Claude (vision)
# ---------------------------------------------------------------------------

def _call_claude(pages: list[bytes], prompt: str, model: str, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    content: list = []
    for idx, page_bytes in enumerate(pages):
        b64 = base64.b64encode(page_bytes).decode()
        if len(pages) > 1:
            content.append({"type": "text", "text": f"الصفحة {idx + 1}:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    content.append({"type": "text", "text": prompt})

    t0 = time.monotonic()
    resp = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )
    usage = resp.usage

    return {
        "text":          resp.content[0].text,
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


# ---------------------------------------------------------------------------
# Backend: Ollama (OpenAI-compatible local, vision models e.g. qwen2.5vl)
# api_key carries the ollama base URL (e.g. http://localhost:11434)
# ---------------------------------------------------------------------------

def _call_ollama(pages: list[bytes], prompt: str, model: str, base_url: str) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url=f"{base_url}/v1", api_key="ollama")

    content: list = []
    for idx, page_bytes in enumerate(pages):
        b64 = base64.b64encode(page_bytes).decode()
        if len(pages) > 1:
            content.append({"type": "text", "text": f"الصفحة {idx + 1}:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=8192,
    )
    usage = resp.usage

    return {
        "text":          resp.choices[0].message.content or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
