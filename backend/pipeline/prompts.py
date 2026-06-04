"""
Prompt builders for the three-stage pipeline.

Stage 1 (vision model): image → raw_text only (OCR)
Stage 2 (text model):   raw_text + 91 doc types → document_type + confidence
Stage 3 (text model):   raw_text + field definitions → extracted JSON fields
"""

from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache

SCHEMA_PATH = Path(__file__).parent.parent / "config" / "schema_v2.json"
FALLBACK_TYPE = "غير_محدد"


@lru_cache(maxsize=1)
def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _type_list_compact() -> str:
    """One line per doc type: key — label (no category to save tokens)."""
    docs = _load_schema()["documents"]
    lines = []
    for key, doc in docs.items():
        label = doc.get("label_ar", key)
        lines.append(f"• {key} — {label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 1 — Vision OCR only (no classification)
# ---------------------------------------------------------------------------

def build_stage1_prompt() -> str:
    """
    Sent with the document image to a vision model.
    Single job: extract all visible text, return it as JSON.
    """
    return """أنت نظام OCR متخصص في استخراج النصوص من الوثائق العربية الرسمية.

## المهمة
استخرج كل النص المرئي في الصورة بدقة كاملة:
- الحفاظ على النص بخطه الأصلي (عربي أو إنجليزي) بدون ترجمة أو تحويل
- الحفاظ على فواصل الأسطر والفقرات
- تضمين النصوص في الأختام والطوابع والتوقيعات والهوامش
- الأرقام والتواريخ كما هي بالضبط

## صيغة الإخراج
أعد JSON فقط — لا نص قبله ولا بعده — يبدأ بـ { وينتهي بـ }:
{
  "raw_text": "النص الكامل المستخرج من الوثيقة"
}"""


# ---------------------------------------------------------------------------
# Stage 2 — Text classification (no image)
# ---------------------------------------------------------------------------

def build_stage2_prompt() -> str:
    """
    Sent with raw_text to a text-only model.
    Single job: decide which of the 91 document types this text belongs to.
    The raw_text is appended after this prompt by the caller.
    """
    type_list = _type_list_compact()
    return f"""أنت نظام تصنيف وثائق دقيق.

## المهمة
اقرأ النص أدناه وحدد نوع الوثيقة من القائمة التالية فقط.
أعد المفتاح بالضبط كما هو مكتوب (مثال: تقرير_طبي وليس "تقرير طبي").

## أنواع الوثائق
{type_list}

**يجب** دائماً اختيار أقرب نوع من القائمة أعلاه — حتى لو لم تكن متأكداً تماماً.
لا تعد أي مفتاح خارج القائمة.

## صيغة الإخراج
أعد JSON فقط — لا نص قبله ولا بعده:
{{
  "document_type": "المفتاح_بالضبط",
  "confidence": "high | medium | low"
}}

## النص:
"""


# ---------------------------------------------------------------------------
# Stage 3 — Field extraction (no image)
# ---------------------------------------------------------------------------

def build_stage3_prompt(doc_type: str) -> str:
    """
    Sent with raw_text to a text-only model.
    Single job: extract only the fields defined for this document type.
    The raw_text is appended after this prompt by the caller.

    Raises ValueError if doc_type is not in the schema.
    """
    schema  = _load_schema()
    doc_def = schema["documents"].get(doc_type)

    if not doc_def:
        raise ValueError(f"Unknown document type: '{doc_type}'")

    label  = doc_def["label_ar"]
    fields = doc_def["fields"]

    field_lines = []
    for f in fields:
        fid    = f["id"]
        flabel = f["label_ar"]
        ftype  = f["type"]
        req    = " [مطلوب]" if f.get("required") else " [اختياري]"

        if ftype == "lookup":
            opts = " | ".join(f.get("options", []))
            hint = f"اختر قيمة واحدة بالضبط من: {opts}"
        elif ftype == "date":
            hint = "تاريخ بصيغة YYYY-MM-DD فقط — بدون أسماء أشهر ولا رموز (م، هـ، /، -) — مثال: 2024-03-15"
        elif ftype == "number":
            hint = "رقم صحيح فقط — أرقام عربية أو غربية بدون أي حروف أو رموز أو فراغات — مثال: 42"
        else:
            hint = "نص"

        field_lines.append(f'  "{fid}": null  // {flabel}{req} — {hint}')

    fields_block = "\n".join(field_lines)

    return f"""أنت نظام استخراج بيانات دقيق من الوثائق الرسمية.

## نوع الوثيقة: {label}

## قواعد الاستخراج
- أعد كل النصوص بخطها الأصلي بدون أي ترجمة
- إذا لم يوجد الحقل في النص أعد null
- lookup: أعد إحدى القيم المذكورة حرفياً — لا تكتب قيمة خارج القائمة
- date: أعد التاريخ بصيغة YYYY-MM-DD دائماً — حوّل أي صيغة أخرى إليها — لا أسماء أشهر ولا رموز (م هـ) ولا علامات (/ -)
- number: أعد رقماً صحيحاً فقط — لا حروف ولا وحدات ولا رموز — (مثال صحيح: 42، خطأ: ٤٢ سنة)

## الحقول المطلوبة
أعد JSON فقط — لا نص قبله ولا بعده:
{{
{fields_block}
}}

## النص:
"""


# ---------------------------------------------------------------------------
# English prompt variants (same logic, English instructions)
# ---------------------------------------------------------------------------

def build_stage1_prompt_en() -> str:
    return """You are an OCR system specialized in extracting text from official Arabic documents.

## Task
Extract all visible text in the image with full accuracy:
- Preserve text in its original script (Arabic or English) — no translation or conversion
- Preserve line breaks and paragraph structure
- Include text in stamps, seals, signatures, and margins
- Numbers and dates exactly as they appear

## Output Format
Return JSON only — no text before or after — starting with { and ending with }:
{
  "raw_text": "The full text extracted from the document"
}"""


def build_stage2_prompt_en() -> str:
    type_list = _type_list_compact()
    return f"""You are a precise document classification system.

## Task
Read the text below and identify the document type from the list below.
You MUST return the Arabic key exactly as it appears before the dash on each line.
The keys are Arabic words — copy them character for character, do not translate them.

## Document Types (format: "arabic_key — label")
{type_list}

You **must** always pick the closest matching key from the list above — even if you are not fully certain.
Never return a key that is not in the list above.

## Output Format
Return JSON only — no text before or after:
{{
  "document_type": "الـمـفـتـاح_العربي_بالضبط",
  "confidence": "high | medium | low"
}}

## Text:
"""


def build_stage3_prompt_en(doc_type: str) -> str:
    schema  = _load_schema()
    doc_def = schema["documents"].get(doc_type)

    if not doc_def:
        raise ValueError(f"Unknown document type: '{doc_type}'")

    label  = doc_def["label_ar"]
    fields = doc_def["fields"]

    field_lines = []
    for f in fields:
        fid    = f["id"]
        flabel = f["label_ar"]
        ftype  = f["type"]
        req    = " [required]" if f.get("required") else " [optional]"

        if ftype == "lookup":
            opts = " | ".join(f.get("options", []))
            hint = f"return exactly one of: {opts}"
        elif ftype == "date":
            hint = "date in YYYY-MM-DD format only — no month names or era markers — e.g. 2024-03-15"
        elif ftype == "number":
            hint = "integer only — no letters, units, or symbols — e.g. 42"
        else:
            hint = "text — preserve original Arabic script, no translation"

        field_lines.append(f'  "{fid}": null  // {flabel}{req} — {hint}')

    fields_block = "\n".join(field_lines)

    return f"""You are a precise data extraction system for official documents.

## Document Type: {label}

## Extraction Rules
- Return all text in its original Arabic script — no translation
- If a field is not present in the text, return null
- lookup: return one of the listed values exactly — do not invent values outside the list
- date: always return YYYY-MM-DD — convert any other format (Arabic months, era markers) to it
- number: return an integer only — no letters, units, or symbols

## Required Fields
Return JSON only — no text before or after:
{{
{fields_block}
}}

## Text:
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_doc_fields(doc_type: str) -> list[dict]:
    schema  = _load_schema()
    doc_def = schema["documents"].get(doc_type)
    return doc_def["fields"] if doc_def else []


def known_types() -> list[str]:
    return list(_load_schema()["documents"].keys())


def known_categories() -> list[str]:
    docs = _load_schema()["documents"]
    seen: dict[str, None] = {}
    for doc in docs.values():
        seen[doc.get("category", "")] = None
    return [c for c in seen if c]


@lru_cache(maxsize=1)
def _category_list_compact() -> str:
    docs = _load_schema()["documents"]
    seen: dict[str, str] = {}
    for doc in docs.values():
        cat = doc.get("category", "")
        label = doc.get("category_label_ar", cat)
        if cat and cat not in seen:
            seen[cat] = label
    return "\n".join(f"• {cat} — {label}" for cat, label in seen.items())


@lru_cache(maxsize=None)
def _types_for_category(category: str) -> str:
    docs = _load_schema()["documents"]
    lines = []
    for key, doc in docs.items():
        if doc.get("category") == category:
            lines.append(f"• {key} — {doc.get('label_ar', key)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 2 two-pass — Pass 1: category  /  Pass 2: specific type
# ---------------------------------------------------------------------------

def build_stage2a_prompt() -> str:
    cat_list = _category_list_compact()
    return f"""أنت نظام تصنيف وثائق.

## المهمة
اقرأ النص وحدد الفئة العامة للوثيقة من القائمة التالية فقط.
أعد مفتاح الفئة بالضبط كما هو مكتوب قبل الشرطة — لا تترجمه.

## الفئات
{cat_list}

**يجب** دائماً اختيار الفئة الأقرب — لا تعد أي قيمة خارج القائمة.

## صيغة الإخراج
أعد JSON فقط — لا نص قبله ولا بعده:
{{
  "category": "مفتاح_الفئة",
  "confidence": "high | medium | low"
}}

## النص:
"""


def build_stage2b_prompt(category: str) -> str:
    type_list = _types_for_category(category) or _type_list_compact()
    return f"""أنت نظام تصنيف وثائق.

## المهمة
اقرأ النص وحدد نوع الوثيقة بالضبط من القائمة التالية.
أعد المفتاح بالضبط كما هو مكتوب قبل الشرطة.

## أنواع الوثائق
{type_list}

**يجب** دائماً اختيار النوع الأقرب — لا تعد أي مفتاح خارج القائمة.

## صيغة الإخراج
أعد JSON فقط — لا نص قبله ولا بعده:
{{
  "document_type": "المفتاح_بالضبط",
  "confidence": "high | medium | low"
}}

## النص:
"""


def build_stage2a_prompt_en() -> str:
    cat_list = _category_list_compact()
    return f"""You are a document classification system.

## Task
Read the text and identify which broad category this document belongs to.
Return the Arabic category key exactly as written before the dash — do not translate it.

## Categories
{cat_list}

You MUST always pick the closest category — never return anything outside this list.

## Output Format
Return JSON only — no text before or after:
{{
  "category": "arabic_category_key",
  "confidence": "high | medium | low"
}}

## Text:
"""


def build_stage2b_prompt_en(category: str) -> str:
    type_list = _types_for_category(category) or _type_list_compact()
    return f"""You are a document classification system.

## Task
Read the text and identify the exact document type from the list below.
Return the Arabic key exactly as written before the dash — copy it character for character, do not translate.

## Document Types
{type_list}

You MUST always pick the closest type — never return anything outside this list.

## Output Format
Return JSON only — no text before or after:
{{
  "document_type": "arabic_key_exactly",
  "confidence": "high | medium | low"
}}

## Text:
"""
