# `/api/mawrid/*` — Laravel-compatible alias routes

This backend also serves the same 3-stage pipeline under the exact route
shapes used by `~/coding/laravel-api-mawrid` (`routes/api.php` +
`MawridController.php`). The API Dog collection documented in that repo's
`apidog.txt` works against this backend unchanged — just point the base URL
at this server (default `http://127.0.0.1:8000`) instead of the Laravel one.

The original `/api/two-stage/*` and `/api/saved` routes are unaffected and
keep serving the React frontend exactly as before; this is a pure addition.

## Routes

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/mawrid/health` | — | `{"status": "ok"}` |
| GET | `/api/mawrid/schema` | — | Full `schema_v2.json` (91 doc types) |
| POST | `/api/mawrid/pipeline/run` | form-data | `file`, `stage1_backend`, `stage2_backend`, `stage3_backend`, `prompt_lang`, `document_type` (skips stage 2 if set), `schema_token` (extra) |
| POST | `/api/mawrid/pipeline/stage1` | form-data | `file`, `stage1_backend`, `prompt_lang` |
| POST | `/api/mawrid/pipeline/stage2` | JSON | `raw_text`, `stage2_backend`, `prompt_lang` |
| POST | `/api/mawrid/pipeline/stage3` | JSON | `raw_text`, `document_type`, `stage3_backend`, `prompt_lang` |
| POST | `/api/mawrid/saved` | form-data | Works here — the equivalent Laravel routes are declared but the controller methods (`saveDocument`, `listDocuments`, `downloadFile`, `deleteDocument`) were never implemented, so they 500 |
| GET | `/api/mawrid/saved` | `?limit&offset` | |
| GET | `/api/mawrid/saved/{id}/file` | — | |
| DELETE | `/api/mawrid/saved/{id}` | — | 204 |
| POST | `/api/mawrid/test/pdf-processor` | form-data | Dev-only, no LLM call — preprocesses a PDF/image and returns page count + sizes |

## Backend prefixes

The Laravel API only supports `groq/<model>` and `gemini/<model>`. This
backend additionally supports `claude/<model>`, `openrouter/<model>`, and
`ollama/<model>` (local, no API key — the "key" slot carries the Ollama base
URL) — usable on any `*_backend` field above.

## Response differences from Laravel

- Stage responses here include extra fields Laravel's don't: `page_images`
  (base64 JPEGs, stage 1 only), `input_tokens`, `output_tokens`, `prompt`.
  Additive — ignore what you don't need.
- Errors under `/api/mawrid/*` are shaped like Laravel's:
  `{"error": "validation_failed"|"server_error", "message": ...}` (422/5xx).
  Routes outside `/api/mawrid/*` keep FastAPI's normal `{"detail": ...}` shape.
