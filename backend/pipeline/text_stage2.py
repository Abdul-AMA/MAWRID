"""
Stage 2 — Text-Only Classification.
Stage 3 — Text-Only Field Extraction.

Both receive raw_text from Stage 1. No image is sent again.
"""

from __future__ import annotations
import json
import re
import time

from pipeline.prompts import (
    build_stage2_prompt, build_stage3_prompt,
    get_doc_fields, FALLBACK_TYPE, known_types,
)


# ---------------------------------------------------------------------------
# Stage 2 — Classify document type from raw text
# ---------------------------------------------------------------------------

def classify_sync(raw_text: str, backend: str, api_key: str) -> dict:
    """
    Send raw_text + 91 doc types to a text model → get document_type back.
    Returns: { document_type, confidence, model, latency_ms, input_tokens, output_tokens }
    """
    prompt = build_stage2_prompt() + raw_text
    raw    = _dispatch(prompt, backend, api_key)
    parsed = _parse_classify_response(raw["text"])
    return {**raw, **parsed}


def _parse_classify_response(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data  = {}
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    doc_type   = data.get("document_type", FALLBACK_TYPE)
    confidence = data.get("confidence", "low")

    if doc_type not in known_types():
        doc_type = FALLBACK_TYPE

    return {
        "document_type": doc_type,
        "confidence":    confidence if confidence in ("high", "medium", "low") else "low",
    }


# ---------------------------------------------------------------------------
# Stage 3 — Extract fields from raw text
# ---------------------------------------------------------------------------

def run_sync(raw_text: str, doc_type: str, backend: str, api_key: str) -> dict:
    """Stage 3: extract structured fields from raw_text for the given doc_type."""
    if doc_type == FALLBACK_TYPE or not doc_type:
        return {"fields": {}, "model": backend, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}

    prompt = build_stage3_prompt(doc_type) + raw_text
    raw    = _dispatch(prompt, backend, api_key)
    return {**raw, "fields": _parse_fields(raw["text"], doc_type)}


async def run(raw_text: str, doc_type: str, backend: str, api_key: str) -> dict:
    return run_sync(raw_text, doc_type, backend, api_key)


# ---------------------------------------------------------------------------
# Shared dispatcher
# ---------------------------------------------------------------------------

def _dispatch(prompt: str, backend: str, api_key: str) -> dict:
    if backend.startswith("openrouter/"):
        return _call_openrouter(prompt, backend[len("openrouter/"):], api_key)
    if backend.startswith("gemini/"):
        return _call_gemini(prompt, backend[len("gemini/"):], api_key)
    if backend.startswith("groq/"):
        return _call_groq(prompt, backend[len("groq/"):], api_key)
    if backend.startswith("openai/"):
        return _call_openai(prompt, backend[len("openai/"):], api_key)
    if backend.startswith("claude/"):
        return _call_claude(prompt, backend[len("claude/"):], api_key)
    if backend.startswith("ollama/"):
        return _call_ollama(prompt, backend[len("ollama/"):], api_key)
    raise ValueError(f"Unsupported backend: {backend}")


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_fields(text: str, doc_type: str) -> dict:
    """
    Parse the model's JSON response into a clean field dict.
    Removes comment annotations that some models may echo back.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Strip inline comments before parsing (// ...)
    cleaned = re.sub(r"//[^\n\"]*", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    # Keep only keys that exist in the schema for this doc type, then sanitize values
    fields_meta = {f["id"]: f for f in get_doc_fields(doc_type)}
    result = {}
    for k, v in data.items():
        if k not in fields_meta:
            continue
        result[k] = _sanitize_field(v, fields_meta[k])
    return result


_AR_DIGIT = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_AR_MONTHS = {
    "يناير": "01", "فبراير": "02", "مارس": "03", "أبريل": "04",
    "مايو": "05", "يونيو": "06", "يوليو": "07", "أغسطس": "08",
    "سبتمبر": "09", "أكتوبر": "10", "نوفمبر": "11", "ديسمبر": "12",
    "كانون الثاني": "01", "شباط": "02", "آذار": "03", "نيسان": "04",
    "أيار": "05", "حزيران": "06", "تموز": "07", "آب": "08",
    "أيلول": "09", "تشرين الأول": "10", "تشرين الثاني": "11", "كانون الأول": "12",
}


def _sanitize_field(value, field_meta: dict):
    if value is None:
        return None
    ftype = field_meta.get("type", "text")

    if ftype == "number":
        s = str(value).translate(_AR_DIGIT)
        m = re.search(r"\d+", s)
        return int(m.group()) if m else None

    if ftype == "date":
        s = str(value).translate(_AR_DIGIT)
        # Replace Arabic month names before stripping era markers (م appears in month names)
        for name, num in _AR_MONTHS.items():
            s = s.replace(name, num)
        # Strip era markers and extra punctuation
        s = re.sub(r"[مهـ]", "", s).strip()
        # Try common patterns → YYYY-MM-DD
        for pat in (
            r"(\d{4})[-/\s](\d{1,2})[-/\s](\d{1,2})",   # YYYY-M-D
            r"(\d{1,2})[-/\s](\d{1,2})[-/\s](\d{4})",   # D-M-YYYY
            r"(\d{1,2})[-/\s](\d{1,2})[-/\s](\d{2})$",  # D-M-YY
        ):
            m = re.search(pat, s)
            if m:
                g = m.groups()
                if len(g[0]) == 4:          # YYYY-M-D
                    y, mo, d = g
                elif len(g[2]) == 4:        # D-M-YYYY
                    d, mo, y = g
                else:                       # D-M-YY
                    d, mo, y = g
                    y = "20" + y
                return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        return s.strip() if s.strip() else None

    if ftype == "lookup":
        options = field_meta.get("options", [])
        if value in options:
            return value
        # Fuzzy: return first option that appears as substring (or None)
        v_lower = str(value).lower()
        for opt in options:
            if opt.lower() in v_lower or v_lower in opt.lower():
                return opt
        return None

    return value


# ---------------------------------------------------------------------------
# Backend: OpenRouter (OpenAI-compatible, text-only)
# ---------------------------------------------------------------------------

def _call_openrouter(prompt: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"X-Title": "MAWRID"},
    )

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
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
# Backend: Google Gemini (text-only)
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, model: str, api_key: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    t0 = time.monotonic()
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=4096),
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
# Backend: Groq (text-only, very fast)
# ---------------------------------------------------------------------------

def _call_groq(prompt: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
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
# Backend: OpenAI (text-only)
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
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
# Backend: Anthropic Claude (text-only)
# ---------------------------------------------------------------------------

def _call_claude(prompt: str, model: str, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    t0 = time.monotonic()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
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
# Backend: Ollama (OpenAI-compatible local, text-only)
# api_key carries the ollama base URL (e.g. http://localhost:11434)
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, model: str, base_url: str) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url=f"{base_url}/v1", api_key="ollama")

    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    usage = resp.usage

    return {
        "text":          resp.choices[0].message.content or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "input_tokens":  usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
