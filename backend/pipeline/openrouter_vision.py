"""
OpenRouter Vision OCR — sends document pages via OpenAI-compatible API and returns extracted text.
Free-tier models with vision support.
"""

from __future__ import annotations

OPENROUTER_MODELS = [
    "baidu/qianfan-ocr-fast:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]

DEFAULT_PROMPT = (
    "Extract all text from this document image exactly as it appears. "
    "Preserve the original layout, line breaks, and paragraph structure. "
    "Return only the extracted text with no additional commentary."
)


def _to_jpeg_pages(file_bytes: bytes) -> list[bytes]:
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


def run_openrouter_ocr(file_bytes: bytes, model: str, prompt: str, api_key: str) -> dict:
    import base64, time
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"X-Title": "MAWRID OCR"},
    )

    t0 = time.monotonic()
    jpeg_pages = _to_jpeg_pages(file_bytes)

    content: list = []
    page_images_b64: list[str] = []

    for idx, jpeg_bytes in enumerate(jpeg_pages):
        b64 = base64.b64encode(jpeg_bytes).decode()
        page_images_b64.append(b64)

        if len(jpeg_pages) > 1:
            content.append({"type": "text", "text": f"Page {idx + 1}:"})

        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    content.append({"type": "text", "text": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=8192,
    )

    usage = response.usage
    return {
        "text":          response.choices[0].message.content or "",
        "model":         model,
        "latency_ms":    round((time.monotonic() - t0) * 1000, 1),
        "page_images":   page_images_b64,
        "input_tokens":  usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
