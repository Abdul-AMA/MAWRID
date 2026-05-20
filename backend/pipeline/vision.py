"""
Vision OCR — sends document pages to Claude as images and returns extracted text.
"""

from __future__ import annotations

CLAUDE_MODELS = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-7",
]

DEFAULT_PROMPT = (
    "Extract all text from this document image exactly as it appears. "
    "Preserve the original layout, line breaks, and paragraph structure. "
    "Return only the extracted text with no additional commentary."
)


def _to_images_vision(file_bytes: bytes) -> list:
    """PDF/image → numpy arrays at 150 DPI (sufficient for Claude vision)."""
    import io, numpy as np
    from PIL import Image as PILImage

    if file_bytes[:4] == b"%PDF":
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(np.array(img))
        doc.close()
        return images

    img = PILImage.open(io.BytesIO(file_bytes)).convert("RGB")
    return [np.array(img)]


def run_vision_ocr(file_bytes: bytes, model: str, prompt: str, api_key: str) -> dict:
    import io, base64, time
    import anthropic
    from PIL import Image as PILImage

    t0 = time.monotonic()
    images = _to_images_vision(file_bytes)

    content: list = []
    page_images_b64: list[str] = []

    for idx, img_array in enumerate(images):
        buf = io.BytesIO()
        PILImage.fromarray(img_array).save(buf, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        page_images_b64.append(img_b64)

        if len(images) > 1:
            content.append({"type": "text", "text": f"Page {idx + 1}:"})

        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64},
        })

    content.append({"type": "text", "text": prompt})

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )

    return {
        "text":          response.content[0].text,
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "page_images":   page_images_b64,
        "input_tokens":  response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
