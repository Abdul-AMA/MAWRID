"""
Stage 1 — OCR.

Backends:
  paddleocr     → PaddleOCR (local, Arabic + English)
  easyocr       → EasyOCR (local, Arabic + English)
  azure_di_read → Azure Document Intelligence Read API  [Step 6]
  vision        → skip OCR; images passed to FL combo
"""

from __future__ import annotations
import asyncio

# ── PaddleOCR singleton (loaded once per worker process) ─────────────────────

PADDLE_CONFIG: dict = {
    "lang":                "ar",
    "use_angle_cls":       True,
    "show_log":            False,
    "det_db_unclip_ratio": 2.25,
    "det_db_thresh":       0.25,
    "det_db_box_thresh":   0.5,
}

# Cache engines by their config so custom params don't discard the default engine.
_engine_cache: dict[tuple, object] = {}


def _get_paddle_engine(overrides: dict | None = None):
    cfg = {**PADDLE_CONFIG, **(overrides or {}), "show_log": False}
    key = tuple(sorted(cfg.items()))
    if key not in _engine_cache:
        from paddleocr import PaddleOCR
        _engine_cache[key] = PaddleOCR(**cfg)
    return _engine_cache[key]


# ── File → image conversion ───────────────────────────────────────────────────

def _to_images(file_bytes: bytes) -> list:
    """Return a list of numpy RGB arrays, one per page."""
    import io
    import numpy as np
    from PIL import Image

    if file_bytes[:4] == b"%PDF":
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(np.array(img))
        doc.close()
        return images

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    import numpy as np
    return [np.array(img)]


# ── Synchronous PaddleOCR call (runs in thread pool from async context) ───────

def _is_arabic(text: str) -> bool:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    total = sum(1 for c in text if c.isalpha())
    return total > 0 and arabic / total > 0.5


def _fix_rtl(text: str) -> str:
    """PaddleOCR reads spatially L→R, so Arabic words come out reversed."""
    return text[::-1] if _is_arabic(text) else text


def _merge_into_lines(detections: list) -> list:
    """
    Merge word-level detections into line-level ones.

    PaddleOCR returns one box per word (or text fragment). We group boxes
    that share the same visual line by comparing their y-centres, then sort
    each group in the correct reading order (RTL for Arabic, LTR for Latin).
    """
    if not detections:
        return []

    def cy(d) -> float:
        ys = [p[1] for p in d["bbox"]]
        return (min(ys) + max(ys)) / 2

    def h(d) -> float:
        ys = [p[1] for p in d["bbox"]]
        return max(ys) - min(ys) + 1

    # Sort top-to-bottom
    dets = sorted(detections, key=cy)

    # Greedy grouping: a new line starts when the gap exceeds 60 % of avg height
    lines: list[list] = [[dets[0]]]
    for d in dets[1:]:
        last = lines[-1]
        avg_h = sum(h(x) for x in last) / len(last)
        if abs(cy(d) - cy(last[-1])) < avg_h * 0.6:
            last.append(d)
        else:
            lines.append([d])

    merged = []
    for idx, line in enumerate(lines):
        text_joined = " ".join(d["text"] for d in line)
        arabic = sum(1 for c in text_joined if "؀" <= c <= "ۿ")
        total  = sum(1 for c in text_joined if c.isalpha())
        rtl    = total > 0 and arabic / total > 0.5

        # Sort words in reading order: RTL → right-most x first; LTR → left-most first
        line_sorted = sorted(
            line,
            key=lambda d: min(p[0] for p in d["bbox"]),
            reverse=rtl,
        )

        all_x = [p[0] for d in line_sorted for p in d["bbox"]]
        all_y = [p[1] for d in line_sorted for p in d["bbox"]]

        merged.append({
            "text":       " ".join(d["text"] for d in line_sorted),
            "confidence": round(sum(d["confidence"] for d in line_sorted) / len(line_sorted), 3),
            "bbox": [
                [int(min(all_x)), int(min(all_y))],
                [int(max(all_x)), int(min(all_y))],
                [int(max(all_x)), int(max(all_y))],
                [int(min(all_x)), int(max(all_y))],
            ],
            "page":  line_sorted[0]["page"],
            "index": idx,
        })

    return merged


def _run_paddleocr_sync(file_bytes: bytes) -> str:
    """Returns flat text string — used by the full pipeline."""
    pages = _run_paddleocr_layout(file_bytes)
    return "\n".join(d["text"] for p in pages for d in p["detections"])


def _run_paddleocr_layout(file_bytes: bytes, params: dict | None = None) -> list:
    """Returns per-page layout data with bboxes and JPEG thumbnails."""
    import io, base64
    from PIL import Image as PILImage

    engine = _get_paddle_engine(params)
    images = _to_images(file_bytes)
    pages = []

    for page_idx, img_array in enumerate(images):
        result = engine.ocr(img_array, cls=True)
        detections = []
        det_idx = 0

        if result:
            for page_result in result:
                if not page_result:
                    continue
                for detection in page_result:
                    if detection and len(detection) >= 2 and detection[1]:
                        bbox = [[int(p[0]), int(p[1])] for p in detection[0]]
                        text = detection[1][0]
                        conf = float(detection[1][1])
                        if text and text.strip():
                            detections.append({
                                "text": _fix_rtl(text.strip()),
                                "confidence": round(conf, 3),
                                "bbox": bbox,
                                "page": page_idx,
                                "index": det_idx,
                            })
                            det_idx += 1

        buf = io.BytesIO()
        PILImage.fromarray(img_array).save(buf, format="JPEG", quality=85)
        pages.append({
            "image_b64": base64.b64encode(buf.getvalue()).decode(),
            "width":      img_array.shape[1],
            "height":     img_array.shape[0],
            "detections": _merge_into_lines(detections),
        })

    return pages


# ── EasyOCR ──────────────────────────────────────────────────────────────────

EASYOCR_DEFAULT_READ_PARAMS: dict = {
    "decoder":          "greedy",
    "beamWidth":        5,
    "batch_size":       1,
    "workers":          0,
    "detail":           1,
    "paragraph":        False,
    "min_size":         10,
    "text_threshold":   0.7,
    "low_text":         0.4,
    "link_threshold":   0.4,
    "canvas_size":      2560,
    "mag_ratio":        1,
    "contrast_ths":     0.1,
    "adjust_contrast":  0.5,
    "slope_ths":        0.1,
    "ycenter_ths":      0.5,
    "height_ths":       0.5,
    "width_ths":        0.5,
    "add_margin":       0.1,
    "x_ths":            1.0,
    "y_ths":            0.5,
    "filter_ths":       0.003,
}

_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(
            lang_list=["ar", "en"],
            gpu=False,
            verbose=False,
        )
    return _easyocr_reader


def _run_easyocr_layout(file_bytes: bytes, params: dict | None = None) -> list:
    import io, base64
    from PIL import Image as PILImage

    allowed = {k: v for k, v in (params or {}).items() if k in EASYOCR_DEFAULT_READ_PARAMS}
    read_params = {**EASYOCR_DEFAULT_READ_PARAMS, **allowed}
    reader = _get_easyocr_reader()
    images = _to_images(file_bytes)
    pages = []

    for page_idx, img_array in enumerate(images):
        raw = reader.readtext(img_array, **read_params)
        detections = []
        for det_idx, item in enumerate(raw):
            bbox_raw, text, conf = item
            if not text or not text.strip():
                continue
            # EasyOCR returns 4-point bbox as [[x,y], ...]
            bbox = [[int(p[0]), int(p[1])] for p in bbox_raw]
            detections.append({
                "text":       text.strip(),
                "confidence": round(float(conf), 3),
                "bbox":       bbox,
                "page":       page_idx,
                "index":      det_idx,
            })

        buf = io.BytesIO()
        PILImage.fromarray(img_array).save(buf, format="JPEG", quality=85)
        pages.append({
            "image_b64": base64.b64encode(buf.getvalue()).decode(),
            "width":      img_array.shape[1],
            "height":     img_array.shape[0],
            "detections": _merge_into_lines(detections),
        })

    return pages


def _run_easyocr_sync(file_bytes: bytes) -> str:
    pages = _run_easyocr_layout(file_bytes)
    return "\n".join(d["text"] for p in pages for d in p["detections"])


# ── Azure stub ────────────────────────────────────────────────────────────────

STUB_TEXT = (
    "محمد أحمد السيد\n"
    "تاريخ الميلاد: 1990/05/15\n"
    "مكان الميلاد: غزة\n"
    "رقم القيد: 123456789\n"
    "تاريخ الإصدار: 2023/01/01\n"
)


def _stub_azure(file_bytes: bytes) -> str:
    return STUB_TEXT  # TODO Step 6: call Azure DI Read API


# ── Public sync interface (used by Celery tasks) ──────────────────────────────

def run_layout(file_bytes: bytes, backend: str, params: dict | None = None) -> list:
    """Return per-page layout data with bboxes. Sync — safe for Celery workers."""
    if backend == "paddleocr":
        return _run_paddleocr_layout(file_bytes, params)
    if backend == "easyocr":
        return _run_easyocr_layout(file_bytes, params)
    raise ValueError(f"run_layout: unsupported backend '{backend}'")


# ── Public async interface ────────────────────────────────────────────────────

async def run(file_bytes: bytes, backend: str) -> str:
    """Return extracted text from the document."""
    if backend == "paddleocr":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_paddleocr_sync, file_bytes)
    if backend == "easyocr":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_easyocr_sync, file_bytes)
    if backend == "azure_di_read":
        return _stub_azure(file_bytes)
    if backend == "vision":
        return ""  # FL combo — images handled by classifier/extractor directly
    raise ValueError(f"Unknown OCR backend: {backend}")
