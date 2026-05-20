"""
Azure Document Intelligence OCR — uses the prebuilt Read/Layout models.
SDK: azure-ai-formrecognizer 3.3.3 (already in requirements-api.txt)
"""

from __future__ import annotations

AZURE_DI_MODELS = [
    "prebuilt-read",
    "prebuilt-layout",
]


def _render_pages(file_bytes: bytes) -> list[str]:
    """Render PDF/image pages to base64 JPEGs for preview."""
    import io, base64
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
            pages.append(base64.b64encode(buf.getvalue()).decode())
        doc.close()
        return pages

    buf = io.BytesIO()
    PILImage.open(io.BytesIO(file_bytes)).convert("RGB").save(buf, format="JPEG", quality=85)
    return [base64.b64encode(buf.getvalue()).decode()]


def run_azure_di_ocr(file_bytes: bytes, model: str, endpoint: str, api_key: str) -> dict:
    import io, time
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential

    t0 = time.monotonic()

    client = DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
    )

    poller = client.begin_analyze_document(model, io.BytesIO(file_bytes))
    result = poller.result()

    # Extract text — paragraphs preserve reading order better than raw content
    if result.paragraphs:
        text = "\n".join(p.content for p in result.paragraphs)
    else:
        text = result.content or ""

    pages_billed = len(result.pages) if result.pages else 1
    page_images  = _render_pages(file_bytes)

    return {
        "text":         text,
        "model":        model,
        "latency_ms":   round((time.monotonic() - t0) * 1000, 1),
        "page_images":  page_images,
        "pages_billed": pages_billed,
    }
