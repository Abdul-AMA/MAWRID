# MAWRID Backend — Laravel Port Specification

## Overview

MAWRID is an AI-powered document intake system for the Municipality of Gaza.
Users upload a PDF or image of an Arabic government document. The system runs a
3-stage LLM pipeline to extract structured data from it.

---

## 1. The 3-Stage Pipeline

```
File upload (PDF or image)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 1 — Vision OCR                                   │
│  Input:   raw file bytes                                │
│  Task:    extract all visible text from the document    │
│  Output:  raw_text, page_images (base64 JPEGs), tokens  │
│  Needs:   vision-capable model (can see images)         │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 2 — Classification                               │
│  Input:   raw_text                                      │
│  Task:    identify which of 91 document types this is   │
│  Output:  document_type (Arabic key), confidence        │
│  Needs:   text-only model is sufficient                 │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 3 — Field Extraction                             │
│  Input:   raw_text + document_type                      │
│  Task:    extract structured fields for that doc type   │
│  Output:  fields{} key→value map, tokens                │
│  Needs:   text-only model is sufficient                 │
└─────────────────────────────────────────────────────────┘
```

All three stages use the same "backend" string (e.g. `groq/llama-4-scout`).
Each stage can independently use a different backend if the user chooses.

---

## 2. Supported Backends

| Prefix | Base URL | Protocol | Notes |
|--------|----------|----------|-------|
| `groq/<model>` | `https://api.groq.com/openai/v1` | OpenAI-compatible | Fast inference |
| `claude/<model>` | `https://api.anthropic.com/v1/messages` | Anthropic REST | Native API |
| `gemini/<model>` | `https://generativelanguage.googleapis.com/v1beta` | Google REST | |
| `openrouter/<model>` | `https://openrouter.ai/api/v1` | OpenAI-compatible | Add header `X-Title: MAWRID` |
| `openai/<model>` | `https://api.openai.com/v1` | OpenAI-compatible | |
| `ollama/<model>` | `{OLLAMA_BASE_URL}/v1` | OpenAI-compatible | Use `"ollama"` as bearer token |

> For `ollama/`, the API key config value is actually the **base URL**
> (e.g. `http://localhost:11434`), not a real key.

### API Key Routing

```
groq/        → GROQ_API_KEY
claude/      → ANTHROPIC_API_KEY
gemini/      → GEMINI_API_KEY
openrouter/  → OPENROUTER_API_KEY
openai/      → OPENAI_API_KEY
ollama/      → OLLAMA_BASE_URL  (used as base URL, not key)
```

---

## 3. API Endpoints

### POST /api/mawrid/pipeline/run

Runs the full 3-stage pipeline on an uploaded document.

**Request** — `multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | file | required | PDF, JPG, PNG, WEBP — max 20 MB |
| `stage1_backend` | string | `groq/meta-llama/llama-4-scout-17b-16e-instruct` | Vision model |
| `stage2_backend` | string | same as above | Classification model |
| `stage3_backend` | string | same as above | Extraction model |
| `prompt_lang` | string | `ar` | `ar` or `en` — language of system prompts |

**Response** — `200 JSON`

```json
{
  "stage1": {
    "raw_text": "النص المستخرج من الوثيقة...",
    "page_images": ["base64encodedJPEG", "..."],
    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "latency_ms": 1240.5,
    "input_tokens": 512,
    "output_tokens": 300,
    "prompt": "..."
  },
  "stage2": {
    "document_type": "شهادة_ميلاد",
    "document_type_label": "شهادة ميلاد",
    "confidence": "high",
    "field_count": 8,
    "model": "...",
    "latency_ms": 820.0,
    "input_tokens": 1100,
    "output_tokens": 25,
    "prompt": "..."
  },
  "stage3": {
    "fields": {
      "الاسم": "محمد أحمد",
      "تاريخ_الميلاد": "1990-05-12",
      "الجنس": "ذكر"
    },
    "model": "...",
    "latency_ms": 640.0,
    "input_tokens": 900,
    "output_tokens": 80,
    "prompt": "..."
  }
}
```

---

### GET /api/mawrid/schema

Returns the full `schema_v2.json` — all 91 document type definitions.

**Response** — `200 JSON`

```json
{
  "documents": {
    "شهادة_ميلاد": {
      "label_ar": "شهادة ميلاد",
      "category": "personal",
      "category_label_ar": "وثائق شخصية",
      "fields": [
        {
          "id": "الاسم",
          "label_ar": "الاسم الكامل",
          "type": "text",
          "required": true
        },
        {
          "id": "تاريخ_الميلاد",
          "label_ar": "تاريخ الميلاد",
          "type": "date",
          "required": true
        },
        {
          "id": "الجنس",
          "label_ar": "الجنس",
          "type": "lookup",
          "options": ["ذكر", "أنثى"],
          "required": true
        }
      ]
    }
    // ... 90 more document types
  }
}
```

**Field types:** `text` · `date` · `number` · `lookup` (lookup always has an `options` array)

---

### POST /api/mawrid/saved

Save a processed document and its extracted fields to the database.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | yes | Original document file |
| `category` | string | yes | e.g. `"personal"` |
| `category_label` | string | yes | e.g. `"وثائق شخصية"` |
| `doc_type` | string | yes | Arabic key e.g. `"شهادة_ميلاد"` |
| `doc_type_label` | string | yes | e.g. `"شهادة ميلاد"` |
| `combo` | string | no | e.g. `"groq+groq+groq"` |
| `confidence` | float | no | Overall confidence score |
| `cost` | float | no | Estimated API cost |
| `latency` | float | no | Total pipeline latency in ms |
| `fields_json` | JSON string | no | Array of field objects (see below) |

`fields_json` shape:
```json
[
  { "field_id": "الاسم", "label_ar": "الاسم الكامل", "value": "محمد", "confidence": 0.95 },
  { "field_id": "تاريخ_الميلاد", "label_ar": "تاريخ الميلاد", "value": "1990-05-12", "confidence": 0.9 }
]
```

**Response** — `201 JSON` — saved document object (same shape as GET /saved records)

---

### GET /api/mawrid/saved

List all saved documents.

**Query parameters:** `limit` (default 100, max 500) · `offset` (default 0)

**Response** — `200 JSON`

```json
{
  "records": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "document.pdf",
      "category": "personal",
      "category_label": "وثائق شخصية",
      "doc_type": "شهادة_ميلاد",
      "doc_type_label": "شهادة ميلاد",
      "combo": "groq+groq+groq",
      "confidence": 0.9,
      "cost": 0.0,
      "latency": 3500.0,
      "created_at": "2026-06-04T12:00:00.000Z",
      "fields": [
        {
          "field_id": "الاسم",
          "label_ar": "الاسم الكامل",
          "value": "محمد أحمد",
          "confidence": 0.0
        }
      ]
    }
  ],
  "total": 42
}
```

---

### GET /api/mawrid/saved/{id}/file

Download the original uploaded file for a saved document.

**Response** — file download (original PDF or image)

**Error** — `404 JSON` if document or file not found

---

### DELETE /api/mawrid/saved/{id}

Delete a saved document, its fields, and its file from disk.

**Response** — `204 No Content`

**Error** — `404 JSON` if document not found

---

### GET /api/mawrid/health

**Response** — `200 JSON`
```json
{ "status": "ok" }
```

---

## 4. Database Schema

### Table: `mawrid_documents`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | varchar(36) | no | UUID, primary key |
| `filename` | varchar(255) | no | Original filename |
| `file_path` | varchar(512) | yes | Absolute path on disk |
| `category` | varchar(64) | no | |
| `category_label` | varchar(128) | no | |
| `doc_type` | varchar(64) | no | Arabic key from schema |
| `doc_type_label` | varchar(128) | no | |
| `combo` | varchar(64) | no | Default `""` |
| `confidence` | float | no | Default `0.0` |
| `cost` | float | no | Default `0.0` |
| `latency` | float | no | Default `0.0` |
| `created_at` | timestamp | — | |
| `updated_at` | timestamp | — | |

### Table: `mawrid_fields`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | bigint | no | Auto-increment primary key |
| `document_id` | varchar(36) | no | FK → `mawrid_documents.id` CASCADE DELETE |
| `field_id` | varchar(64) | no | Matches schema field `id` |
| `label_ar` | varchar(128) | no | |
| `value` | text | yes | Extracted value |
| `confidence` | float | no | Default `0.0` |

---

## 5. Prompt System

All prompts are Arabic by default. English variants are used when `prompt_lang=en`.

### Stage 1 Prompt (sent with images)

Instructs the model: extract all visible text, preserve original script, include stamps
and signatures, preserve line breaks. Return only:

```json
{ "raw_text": "full extracted text" }
```

### Stage 2 Prompt (text only)

Sends all 91 document types as a bullet list:
```
• شهادة_ميلاد — شهادة ميلاد
• بطاقة_هوية — بطاقة هوية وطنية
... (91 total)
```
Instructs model to return the exact Arabic key, nothing else:
```json
{ "document_type": "شهادة_ميلاد", "confidence": "high | medium | low" }
```

**Two-pass variant** (lower token cost, optional):
- Pass A: pick one of ~9 broad categories from a shorter list
- Pass B: pick exact doc type from only that category's subset (~5–15 types)
- Combine latency + token counts from both passes

### Stage 3 Prompt (text only)

Sends field definitions for the identified document type with extraction rules:
```
"الاسم": null  // الاسم الكامل [مطلوب] — نص
"تاريخ_الميلاد": null  // تاريخ الميلاد [مطلوب] — تاريخ بصيغة YYYY-MM-DD
"الجنس": null  // الجنس [مطلوب] — اختر قيمة واحدة من: ذكر | أنثى
```
Model fills in the values and returns the JSON object.

---

## 6. Response Parsing

Every model response goes through this cleanup before JSON parsing:

1. Strip markdown fences (` ```json ... ``` `)
2. Strip trailing backticks
3. For field extraction only: also strip `// comment` annotations
4. Try `json_decode()` — if it fails, regex-extract the first `{...}` block and retry

### Classification fuzzy matching

If the returned `document_type` is not in the known 91 types, apply fuzzy matching:

1. **Exact** case-insensitive match
2. **Substring**: known type contains candidate, or candidate contains known type
3. **Character overlap**: pick the type with the most shared characters

Fallback type if all else fails: `"غير_محدد"` (undefined).
If Stage 2 returns `"غير_محدد"`, Stage 3 is **skipped** and returns empty fields.

---

## 7. Field Value Sanitization

After extraction, each value is sanitized based on its schema type:

### `number`
- Convert Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) to Western (0123456789)
- Extract first integer from the string
- Return as integer, or `null` if none found

### `date`
- Convert Arabic-Indic digits
- Replace Arabic month names with numeric equivalents:
  - يناير→01, فبراير→02, مارس→03, أبريل→04, مايو→05, يونيو→06
  - يوليو→07, أغسطس→08, سبتمبر→09, أكتوبر→10, نوفمبر→11, ديسمبر→12
  - كانون الثاني→01, شباط→02, آذار→03, نيسان→04, أيار→05, حزيران→06
  - تموز→07, آب→08, أيلول→09, تشرين الأول→10, تشرين الثاني→11, كانون الأول→12
- Strip era markers: `م` `هـ` `ـ`
- Match and normalize to `YYYY-MM-DD`:
  - Pattern `YYYY-M-D` → direct
  - Pattern `D-M-YYYY` → reorder
  - Pattern `D-M-YY` → prefix year with `20`

### `lookup`
- Check if value exactly matches one of the schema `options`
- If not, try case-insensitive substring match (either direction)
- If still no match → return `null`

### `text`
- Return as-is

---

## 8. File Processing (PDF → JPEG Pages)

**Server requirements:** `php-imagick` extension + `ghostscript` system package

```
apt install ghostscript
apt install php-imagick
```

**Logic:**
1. If file bytes start with `%PDF` → PDF mode
   - Use Imagick at 200 DPI to render each page as an image
2. Otherwise → single image mode
3. Per page:
   - Convert to grayscale
   - Resize to max 600 px wide (preserve aspect ratio, Lanczos filter)
   - Boost contrast (sigmoidal contrast)
   - Save as JPEG, quality 85, strip metadata

**ImageMagick policy:** The default ImageMagick security policy blocks PDF reads.
Add this to `/etc/ImageMagick-7/policy.xml`:
```xml
<policy domain="coder" rights="read|write" pattern="PDF" />
```

---

## 9. Environment Variables

```env
# App
APP_KEY=
APP_URL=http://localhost:8080

# Database (SQLite for dev, MySQL/Postgres for prod)
DB_CONNECTION=sqlite
# DB_CONNECTION=mysql
# DB_HOST=127.0.0.1
# DB_DATABASE=mawrid
# DB_USERNAME=mawrid
# DB_PASSWORD=secret

# AI Provider keys
GROQ_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

# MAWRID config
MAWRID_DEFAULT_BACKEND=groq/meta-llama/llama-4-scout-17b-16e-instruct
MAWRID_SCHEMA_PATH=/var/www/html/config/mawrid_schema_v2.json
MAWRID_UPLOADS_PATH=/var/www/html/storage/app/mawrid/uploads
```

---

## 10. Key Constraints

- **Stage 1 requires a vision-capable model.** Text-only models will fail.
- **Stages 2 and 3 only receive text**, never images. OCR output only.
- **`schema_v2.json` must be present** at `MAWRID_SCHEMA_PATH`. It is the source
  of truth for all 91 document types, field definitions, and category lists.
- **File storage path:** `{MAWRID_UPLOADS_PATH}/{uuid}/{original_filename}`
- **Max file size:** 20 MB
- **HTTP timeout per LLM call:** 120 seconds
- **All API responses are JSON** with Arabic content — ensure UTF-8 throughout.
- **CORS:** Allow your frontend origin on all `/api/mawrid/*` routes.

---

## 11. Suggested Laravel File Structure

```
app/
├── Http/Controllers/
│   └── MawridController.php       — all 7 endpoints
├── Models/
│   ├── MawridDocument.php          — mawrid_documents table
│   └── MawridField.php             — mawrid_fields table
└── Services/
    └── Mawrid/
        ├── Pipeline.php            — orchestrates 3 stages, resolves API keys
        ├── Prompts.php             — all prompt builders (loads schema_v2.json)
        ├── PdfProcessor.php        — PDF/image → JPEG pages via Imagick
        ├── VisionStage1.php        — Stage 1, all providers
        └── TextStage2.php          — Stage 2 + Stage 3, all providers

config/
├── mawrid.php                      — API keys, paths, default backend
└── mawrid_schema_v2.json           — 91 document type definitions (attach this file)

database/migrations/
└── xxxx_create_mawrid_tables.php   — mawrid_documents + mawrid_fields

routes/
└── api.php                         — register all /api/mawrid/* routes
```

---

## 12. Attached File

Include `mawrid_schema_v2.json` alongside this document.
It contains the complete definitions for all 91 document types including field IDs,
Arabic labels, field types, lookup options, and category groupings.
The backend must load this file to build Stage 2 and Stage 3 prompts at runtime.
