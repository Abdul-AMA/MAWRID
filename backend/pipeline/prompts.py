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
    """One line per doc type: key — label (category)."""
    docs = _load_schema()["documents"]
    lines = []
    for key, doc in docs.items():
        label    = doc.get("label_ar", key)
        category = doc.get("category_label_ar") or doc.get("category", "")
        lines.append(f"• {key} — {label} ({category})")
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

إذا لم يتطابق النص مع أي نوع اذكر: {FALLBACK_TYPE}

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
# Helpers
# ---------------------------------------------------------------------------

def get_doc_fields(doc_type: str) -> list[dict]:
    schema  = _load_schema()
    doc_def = schema["documents"].get(doc_type)
    return doc_def["fields"] if doc_def else []


def known_types() -> list[str]:
    return list(_load_schema()["documents"].keys())
