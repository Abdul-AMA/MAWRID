#!/usr/bin/env python3
"""
Strip baidu/Unlimited-OCR's layout markup (<|det|>...<|/det|> tags, bounding
boxes, raw <table> HTML, LaTeX equation wrappers) down to plain readable text.

    python scripts/clean_ocr_output.py data/unlimited_ocr_out/0003.txt
    python scripts/clean_ocr_output.py data/unlimited_ocr_out/0003.txt -o data/unlimited_ocr_out/0003.clean.txt
"""

from __future__ import annotations
import argparse
import re
from pathlib import Path

# well-formed: <|det|>label [bbox]<|/det|>
_DET_TAG = re.compile(r"<\|det\|>\s*[\w_]+\s*\[[^\]]*\]\s*<\|/det\|>")
# malformed but still closed, e.g. <|det|>image_1, 626, 415, 781]<|/det|>
_DET_TAG_LOOSE = re.compile(r"<\|det\|>.*?<\|/det\|>")
# truncated mid-generation, never closed, e.g. <|det|>page_number [706,
_DET_TAG_DANGLING = re.compile(r"<\|det\|>.*")
_DET_CLOSE_STRAY = re.compile(r"<\|/det\|>")

_TABLE_ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_TABLE_CELL = re.compile(r"<td>(.*?)</td>", re.DOTALL)
_TABLE_TAGS = re.compile(r"</?table>")

_LATEX_DOUBLE_BRACE = re.compile(r"\{\{([^{}]*)\}\}")
_LATEX_TEXT_CMD = re.compile(r"\\text\s*\{([^{}]*)\}")
_LATEX_WRAP_CMD = re.compile(r"\\[a-zA-Z]+\s*\{([^{}]*)\}")  # \overline{...}, etc.
_LATEX_DELIMS = re.compile(r"\\[\[\]()]")
_LATEX_STRAY_CMD = re.compile(r"\\[a-zA-Z]+")


def _clean_table(match: re.Match) -> str:
    table_html = match.group(0)
    rows = []
    for row_html in _TABLE_ROW.findall(table_html):
        cells = [re.sub(r"\s+", " ", c).strip() for c in _TABLE_CELL.findall(row_html)]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _clean_latex(text: str) -> str:
    text = _LATEX_DOUBLE_BRACE.sub(r"\1", text)
    text = _LATEX_TEXT_CMD.sub(r"\1", text)
    text = _LATEX_WRAP_CMD.sub(r"\1", text)
    text = _LATEX_DELIMS.sub("", text)
    text = _LATEX_STRAY_CMD.sub("", text)
    return text


def clean_ocr_text(text: str) -> str:
    text = _DET_TAG.sub("", text)
    text = _DET_TAG_LOOSE.sub("", text)
    text = _DET_TAG_DANGLING.sub("", text)
    text = _DET_CLOSE_STRAY.sub("", text)

    if "<table>" in text:
        text = re.sub(r"<table>.*?</table>", _clean_table, text, flags=re.DOTALL)
        text = _TABLE_TAGS.sub("", text)

    text = _clean_latex(text)

    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip() not in ("", ".")]
    return "\n".join(lines).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="raw OCR .txt file to clean")
    ap.add_argument("-o", "--output", help="write cleaned text here (default: print to stdout)")
    args = ap.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    cleaned = clean_ocr_text(raw)

    if args.output:
        Path(args.output).write_text(cleaned, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(cleaned)


if __name__ == "__main__":
    main()
