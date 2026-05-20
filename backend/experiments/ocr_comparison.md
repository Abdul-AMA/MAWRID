# OCR Approach Comparison — Gaza Municipality Documents

**Document tested:** قرار رئيس بلدية غزة رقم 2025/14 (employee qualification allowance decision)
**Date:** 2026-05-10

---

## Summary Table

| Metric | PaddleOCR (local) | EasyOCR (local) | Claude Haiku 4.5 (API) |
|---|---|---|---|
| **Latency** | 6.5 s | TBD | 15.5 s |
| **Cost per doc** | ~$0.00 (local) | ~$0.00 (local) | ~$0.01 |
| **Text quality** | Poor — broken words, garbled Arabic | TBD | Excellent — clean, accurate |
| **Structure output** | None — flat noisy text | TBD | Full markdown with table |
| **Table extraction** | Failed | TBD | Correct |
| **Arabic accuracy** | Low (many OCR errors) | TBD | High |
| **Runs offline** | Yes | Yes | No (API call) |
| **Setup complexity** | High | Medium | Minimal |

---

## PaddleOCR Config Used

```
use_angle_cls:       true
det_db_unclip_ratio: 2.25
det_db_thresh:       0.25
det_db_box_thresh:   0.5
```

### PaddleOCR Raw Output (excerpt)

```
نوع القرار: قرارئيس بلدية
2025/14 القرار رقم Municipality of Gaza
التاريخ 4 :مارس02
1521(قرارقرئيسبرئي بلرغ
ارمات الكوارك تاري?/2 ت 0/تنا نلمت بللدية -وح rالادع رقم  من اللائحة تننيني ن يحمل درجة
```

**Problems observed:**
- Words fused together (e.g. `قرارقرئيسبرئي`)
- Random characters injected (`?`, `r`, mixed Latin)
- Dates broken (`تاري?/2 ت 0/`)
- Table data completely lost
- Right-to-left ordering sometimes reversed

---

## Claude Haiku 4.5 Output (excerpt)

```markdown
| م. | الرقم | الاسم | الوظيفة | المؤهل العلمي | ...
|---|---|---|---|---|
| 1 | 2705 | رشدي عاطف رشدي خلف | كاتف بقسم الأمن والكوارث | ماجستير في إدارة الأزمات والكوارث | 200 | ...
```

**Strengths:**
- Accurate Arabic word boundaries
- Table reconstructed correctly
- Dates parsed cleanly (`24 مارس 2025`)
- Document structure (headers, numbered clauses) preserved
- Contact info block extracted

---

## EasyOCR — Full Parameter Reference

EasyOCR splits into **Reader init** (loaded once) and **readtext()** (called per image).

### Reader Initialization Parameters

```python
import easyocr

reader = easyocr.Reader(
    lang_list           = ['ar', 'en'],  # language codes — must include ALL langs in doc
    gpu                 = False,          # True for CUDA GPU acceleration
    model_storage_directory = None,       # custom path for downloaded model weights
    download_enabled    = True,           # allow auto-downloading models
    recog_network       = 'standard',     # recognition network: 'standard' or custom
    detector            = True,           # run text detection (disable if providing your own boxes)
    recognizer          = True,           # run text recognition
    verbose             = False,          # print download/init logs
)
```

| Param | Default | Notes |
|---|---|---|
| `lang_list` | required | `['ar']` Arabic only; `['ar','en']` bilingual. Arabic needs English for numerals in mixed docs |
| `gpu` | `False` | set `True` if CUDA available — major speed boost |
| `model_storage_directory` | `~/.EasyOCR/` | set to local path to avoid re-downloads |
| `recog_network` | `'standard'` | can swap for fine-tuned models |
| `detector` | `True` | CRAFT text detector |
| `recognizer` | `True` | CRNN-based recognizer |

---

### readtext() Parameters — Complete Reference

```python
results = reader.readtext(
    image,                          # np.ndarray, file path, or bytes

    # ── Decoder ──────────────────────────────────────────────────────────
    decoder             = 'greedy',     # 'greedy' | 'beamsearch' | 'wordbeamsearch'
    beamWidth           = 5,            # beam width (only for beamsearch/wordbeamsearch)

    # ── Batching ─────────────────────────────────────────────────────────
    batch_size          = 1,            # recognition batch size (increase for GPU)
    workers             = 0,            # dataloader workers

    # ── Character filtering ───────────────────────────────────────────────
    allowlist           = None,         # string of allowed chars e.g. '0123456789'
    blocklist           = None,         # string of blocked chars

    # ── Output format ────────────────────────────────────────────────────
    detail              = 1,            # 1 = (bbox, text, confidence); 0 = text only
    paragraph           = False,        # merge results into paragraphs
    output_format       = 'standard',   # 'standard' | 'dict'

    # ── Detection sensitivity ─────────────────────────────────────────────
    min_size            = 10,           # minimum text box height in pixels
    text_threshold      = 0.7,          # confidence to keep a detection (0–1)
    low_text            = 0.4,          # low-bound score for text region
    link_threshold      = 0.4,          # affinity score between adjacent chars
    canvas_size         = 2560,         # max image dimension before resize
    mag_ratio           = 1,            # image magnification before detection

    # ── Contrast handling ─────────────────────────────────────────────────
    contrast_ths        = 0.1,          # if contrast below this, re-run with adjust_contrast
    adjust_contrast     = 0.5,          # target contrast level for low-contrast retry

    # ── Line grouping ─────────────────────────────────────────────────────
    slope_ths           = 0.1,          # max slope to group into same line
    ycenter_ths         = 0.5,          # y-center difference threshold for same line
    height_ths          = 0.5,          # height ratio to merge boxes
    width_ths           = 0.5,          # horizontal gap to merge same-line boxes (relative to height)
    add_margin          = 0.1,          # expand bounding boxes by fraction before recognition
    x_ths               = 1.0,          # max horizontal gap before splitting into two boxes
    y_ths               = 0.5,          # max vertical gap before splitting into two boxes

    # ── Rotation ─────────────────────────────────────────────────────────
    rotation_info       = None,         # list of angles to try e.g. [90, 180, 270]

    # ── Filtering ─────────────────────────────────────────────────────────
    filter_ths          = 0.003,        # score map filter threshold (lower = keep more)
)
```

---

### Test Configs — Sweep These

Run the document through each config and record quality + latency.

#### Config A — Baseline (defaults)
```python
reader = easyocr.Reader(['ar', 'en'], gpu=False)
results = reader.readtext(image)
# decoder='greedy', text_threshold=0.7, mag_ratio=1
```

#### Config B — Beam search decoder (higher accuracy, slower)
```python
results = reader.readtext(
    image,
    decoder    = 'beamsearch',
    beamWidth  = 5,
)
```

#### Config C — Magnification boost (helps small/dense text)
```python
results = reader.readtext(
    image,
    mag_ratio  = 1.5,   # upscale before detection
    canvas_size = 3840,  # allow larger canvas
)
```

#### Config D — Aggressive detection (catch faint text)
```python
results = reader.readtext(
    image,
    text_threshold = 0.5,   # lower → keep weaker detections
    low_text       = 0.3,
    link_threshold = 0.3,
    contrast_ths   = 0.2,   # retry contrast fix more aggressively
    adjust_contrast = 0.6,
)
```

#### Config E — Tight line grouping (fix merged lines)
```python
results = reader.readtext(
    image,
    width_ths   = 0.3,   # smaller → split merged words more aggressively
    add_margin  = 0.05,  # tighter crop before recognition
    slope_ths   = 0.05,  # stricter line alignment
)
```

#### Config F — Paragraph mode + beam (closest to Haiku output)
```python
results = reader.readtext(
    image,
    decoder    = 'beamsearch',
    beamWidth  = 5,
    paragraph  = True,
    mag_ratio  = 1.5,
    text_threshold = 0.6,
)
```

#### Config G — GPU + large batch (if CUDA available)
```python
reader = easyocr.Reader(['ar', 'en'], gpu=True)
results = reader.readtext(
    image,
    decoder    = 'beamsearch',
    beamWidth  = 5,
    batch_size = 8,
    workers    = 4,
    mag_ratio  = 1.5,
)
```

---

### EasyOCR Results Log

Fill in after running each config on the test document.

| Config | Latency (s) | Arabic accuracy (subjective 1–5) | Table extracted | Notes |
|---|---|---|---|---|
| A — Baseline | | | | |
| B — Beamsearch | | | | |
| C — mag_ratio 1.5 | | | | |
| D — Aggressive detection | | | | |
| E — Tight grouping | | | | |
| F — Paragraph + beam | | | | |
| G — GPU batch | | | | |

---

## PaddleOCR Improvement Levers

### 1. Language model — highest impact
```python
# Current (likely default 'en' or generic)
ocr = PaddleOCR(lang='en')

# Switch to Arabic-specific model
ocr = PaddleOCR(lang='ar', use_angle_cls=True)
```
PaddleOCR ships an Arabic rec model (`arabic`) trained on RTL text. This alone should cut character errors significantly.

### 2. Detection thresholds
```
# Current config vs tighter suggestions
det_db_thresh:       0.25  → try 0.3–0.4   (reduce false positives)
det_db_box_thresh:   0.5   → try 0.5–0.6   (keep)
det_db_unclip_ratio: 2.25  → try 1.6–2.0   (less aggressive box expansion for dense Arabic)
```

### 3. Image preprocessing before PaddleOCR
Arabic government scans often have low contrast and slight skew.
```python
import cv2
import numpy as np

def preprocess(img_path):
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Upscale if DPI < 200
    h, w = gray.shape
    if w < 1500:
        gray = cv2.resize(gray, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
    # Adaptive threshold instead of raw scan
    binary = cv2.adaptiveThreshold(gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    return binary
```

### 4. Post-processing raw OCR with a cheap LLM (hybrid approach)
Run PaddleOCR for speed/cost, then send the dirty text to Haiku to clean and structure it.
Estimated cost per doc with hybrid: ~$0.003–0.005 (shorter prompt, raw text not image).

### 5. PP-OCRv4 server model
```python
# Use the larger server-grade detection + rec models
ocr = PaddleOCR(
    lang='ar',
    det_model_dir='path/to/PP-OCRv4_server_det',
    rec_model_dir='path/to/PP-OCRv4_server_rec',
    use_angle_cls=True,
)
```

---

## Recommended Strategy

| Volume / Budget | Recommended approach |
|---|---|
| Low volume, quality critical | Haiku (vision) directly |
| High volume, tight budget | PaddleOCR (ar) + preprocess → Haiku cleanup |
| High volume, offline required | PaddleOCR (ar) + local LLM (e.g. Qwen2-VL) |
| Accuracy benchmark target | Compare PP-OCRv4 ar vs Haiku on 20-doc gold set |

---

## Cost Projection at Scale

| Docs/month | Haiku only | Hybrid (OCR + cleanup) | PaddleOCR only |
|---|---|---|---|
| 100 | $1.00 | ~$0.40 | $0.00 |
| 1,000 | $10.00 | ~$4.00 | $0.00 |
| 10,000 | $100.00 | ~$40.00 | $0.00 |

*Hybrid estimate assumes 60% token reduction from passing text instead of image.*
