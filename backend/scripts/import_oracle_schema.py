"""
One-shot script: transforms the flat Oracle query export into form_schemas.json.

Input : /home/abood/Desktop/_SELECT_...json  (flat rows from Oracle)
Output: backend/config/form_schemas.json      (hierarchical schema)

Run once:
    python backend/scripts/import_oracle_schema.py
"""

from __future__ import annotations
import json
import re
from collections import defaultdict, OrderedDict
from pathlib import Path

INPUT_PATH = Path("/home/abood/Desktop/_SELECT_c_CATEGORY_NAME_d_doc_name_AS_doc_name_f_FIELD_NAME_AS_d_202605061453.json")
OUTPUT_PATH = Path(__file__).parent.parent / "config" / "form_schemas.json"

FIELD_TYPE_MAP = {
    "text":   "string",
    "date":   "date",
    "number": "number",
    "lookup": "enum",
    "var":    "string",
}

# 9 categories — short English IDs for use as keys and in the classifier prompt
CATEGORY_ID_MAP = {
    "اجراءات التوظيف":              "employment_procedures",
    "الأوراق الثبوتية والشخصية":    "personal_documents",
    "السيرة الذاتية":                "cv",
    "الشهادات العلمية":              "academic_credentials",
    "العقوبات":                      "disciplinary",
    "القرارات والأوامر الإدارية":    "admin_orders",
    "الملف الصحي":                   "health_file",
    "تقييم الموظف":                  "employee_evaluation",
    "كشوفات ومراسلات وكتب":          "correspondence",
}


def slugify(text: str) -> str:
    """Stable snake_case ID from Arabic text (keeps Arabic letters + digits)."""
    text = text.strip()
    # collapse all whitespace runs → single underscore
    text = re.sub(r"[\s\t\n\r]+", "_", text)
    # drop everything that isn't Arabic, ASCII alphanumeric, or underscore
    text = re.sub(r"[^\w؀-ۿ]", "", text)
    # collapse multiple underscores
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def parse_constants(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [v.strip() for v in re.split(r",\s*|\n", raw) if v.strip()]


def main() -> None:
    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = list(raw.values())[0]

    # ── build: category_name → doc_name → ordered fields ──────────────────
    # Using OrderedDict to preserve Oracle row order
    tree: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    seen_fields: dict[tuple, bool] = {}  # (doc_name, field_id) → True

    for row in rows:
        cat = row["CATEGORY_NAME"].strip()
        doc = row["DOC_NAME"].strip()
        field_name = row["DOCUMENT_FIELDS"].strip()
        field_type = FIELD_TYPE_MAP.get(row["FIELD_TYPE"], "string")
        constants = row["CONSTANT_NAMES"]

        field_id = slugify(field_name)
        dedup_key = (doc, field_id)

        if dedup_key in seen_fields:
            continue  # skip exact duplicates within same doc
        seen_fields[dedup_key] = True

        field: dict = {
            "id":       field_id,
            "label_ar": field_name,
            "data_type": field_type,
            "required": True,
        }
        if field_type == "enum":
            field["values"] = parse_constants(constants)

        tree[cat][doc].append(field)

    # ── build final form_schemas ───────────────────────────────────────────
    # Top-level key = doc_type_id (Arabic slug, globally unique since no doc
    # appears in more than one category).
    schemas: dict = {}
    categories_meta: dict = {}

    for cat_name, docs in tree.items():
        cat_id = CATEGORY_ID_MAP.get(cat_name)
        if cat_id is None:
            # Fallback: shouldn't happen if CATEGORY_ID_MAP is complete
            cat_id = slugify(cat_name)
            print(f"WARNING: unmapped category '{cat_name}' → '{cat_id}'")

        categories_meta[cat_id] = {"label_ar": cat_name}

        for doc_name, fields in docs.items():
            doc_id = slugify(doc_name)
            schemas[doc_id] = {
                "label_ar":      doc_name,
                "category":      cat_id,
                "category_label_ar": cat_name,
                "fields":        fields,
            }

    # Wrap with a top-level envelope so callers can also enumerate categories
    output = {
        "_categories": categories_meta,
        **schemas,
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written {OUTPUT_PATH}")
    print(f"  Categories : {len(categories_meta)}")
    print(f"  Doc types  : {len(schemas)}")
    total_fields = sum(len(s["fields"]) for s in schemas.values())
    print(f"  Total fields: {total_fields}")


if __name__ == "__main__":
    main()
