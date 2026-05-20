"""
Gemini Vision OCR — sends document pages to Gemini as images and returns extracted text.
"""

from __future__ import annotations

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
]

DEFAULT_PROMPT = (
    "Extract all text from this document image exactly as it appears. "
    "Preserve the original layout, line breaks, and paragraph structure. "
    "Return only the extracted text with no additional commentary."
)


def _to_jpeg_pages(file_bytes: bytes) -> list[bytes]:
    """PDF/image → list of JPEG bytes at 150 DPI."""
    import io
    from PIL import Image as PILImage

    if file_bytes[:4] == b"%PDF":
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            pages.append(buf.getvalue())
        doc.close()
        return pages

    buf = io.BytesIO()
    PILImage.open(io.BytesIO(file_bytes)).convert("RGB").save(buf, format="JPEG", quality=85)
    return [buf.getvalue()]


def run_gemini_ocr(file_bytes: bytes, model: str, prompt: str, api_key: str) -> dict:
    import base64, time
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    t0 = time.monotonic()
    jpeg_pages = _to_jpeg_pages(file_bytes)

    parts: list = []
    page_images_b64: list[str] = []

    for idx, jpeg_bytes in enumerate(jpeg_pages):
        page_images_b64.append(base64.b64encode(jpeg_bytes).decode())

        if len(jpeg_pages) > 1:
            parts.append(f"Page {idx + 1}:")

        parts.append(
            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
        )

    parts.append(prompt)

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(max_output_tokens=8192),
    )

    usage = response.usage_metadata
    return {
        "text":          response.text,
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "page_images":   page_images_b64,
        "input_tokens":  usage.prompt_token_count or 0,
        "output_tokens": usage.candidates_token_count or 0,
    }
