#!/usr/bin/env python3
"""
Standalone trial of baidu/Unlimited-OCR (https://huggingface.co/baidu/Unlimited-OCR)
against the MAWRID Arabic document corpus. Not wired into the production
pipeline — this is purely to judge OCR quality before deciding whether to
add it as a Stage 1 backend.

Run inside the isolated .venv-ocr (see scripts/requirements-unlimited-ocr.txt
for why — the model's vendored modeling code is pinned to transformers
4.57.1, incompatible with the project's main .venv which has transformers 5.x):

    .venv-ocr/bin/python scripts/try_unlimited_ocr.py --input data/processed_images/0005 --limit 1 --low-vram

Accepts a single image, a PDF, or a directory of page images as --input.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

_ARABIC_RE = re.compile(r"[؀-ۿ]")


def arabic_char_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(1 for c in letters if _ARABIC_RE.match(c))
    return round(arabic / len(letters), 4)


def render_full_res(file_bytes: bytes) -> list[bytes]:
    """PDF -> one RGB JPEG per page at dpi=200, no grayscale/downscale/contrast.
    Images pass through unchanged. Bypasses the 600px-wide downscale that
    pipeline.vision_stage1.to_pages applies for the LLM-API path — a 3B local
    OCR model may benefit from more pixels than a cloud vision model needs."""
    import io
    import fitz
    from PIL import Image as PILImage

    if file_bytes[:4] != b"%PDF":
        return [file_bytes]

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        pages.append(buf.getvalue())
    doc.close()
    return pages


def load_pages(input_path: Path, full_res: bool) -> tuple[str, list[bytes]]:
    """Returns (doc_id, [jpeg_bytes, ...])."""
    if input_path.is_dir():
        files = sorted(
            p for p in input_path.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")
        )
        if not files:
            raise ValueError(f"No image files found in {input_path}")
        return input_path.name, [f.read_bytes() for f in files]

    file_bytes = input_path.read_bytes()
    doc_id = input_path.stem

    if full_res:
        return doc_id, render_full_res(file_bytes)

    from pipeline.vision_stage1 import to_pages
    return doc_id, to_pages(file_bytes)


def load_model(model_name: str = "baidu/Unlimited-OCR", four_bit: bool = False):
    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    if four_bit:
        from transformers import BitsAndBytesConfig
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        )
        model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_safetensors=True,
            quantization_config=quant_config,
            device_map="auto",
        )
        model = model.eval()
    else:
        model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
        )
        model = model.eval().cuda()
    return tokenizer, model


def run_page(tokenizer, model, image_path: str, args) -> str:
    import torch

    base_size = 640 if args.low_vram else args.base_size
    image_size = 512 if args.low_vram else args.image_size
    crop_mode = False if (args.low_vram or args.no_crop) else True

    with torch.inference_mode():
        out = model.infer(
            tokenizer,
            prompt=args.prompt,
            image_file=image_path,
            output_path=args.out,
            base_size=base_size,
            image_size=image_size,
            crop_mode=crop_mode,
            max_length=args.max_length,
            no_repeat_ngram_size=args.no_repeat_ngram,
            temperature=args.temperature,
            eval_mode=True,  # without this, infer() streams to stdout but returns None
        )
    torch.cuda.empty_cache()
    return out if isinstance(out, str) else str(out)


def run_multi(tokenizer, model, image_paths: list[str], args) -> str:
    import torch

    image_size = 512 if args.low_vram else args.image_size

    with torch.inference_mode():
        out = model.infer_multi(
            tokenizer,
            prompt=args.prompt,
            image_files=image_paths,
            output_path=args.out,
            image_size=image_size,
            max_length=args.max_length,
            no_repeat_ngram_size=args.no_repeat_ngram,
            temperature=args.temperature,
        )
    # infer_multi always returns (outputs, output_tokens), not a bare string
    out = out[0] if isinstance(out, tuple) else out
    torch.cuda.empty_cache()
    return out if isinstance(out, str) else str(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(REPO_ROOT / "data" / "processed_images" / "0005"))
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "unlimited_ocr_out"))
    ap.add_argument("--prompt", default="<image>document parsing.")
    ap.add_argument("--base-size", type=int, default=1024)
    ap.add_argument("--image-size", type=int, default=640)
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--multi", action="store_true", help="run infer_multi over all pages in one call")
    ap.add_argument("--low-vram", action="store_true", help="base_size=640, image_size=512, crop off (8GB VRAM)")
    ap.add_argument("--max-length", type=int, default=32768)
    ap.add_argument("--no-repeat-ngram", type=int, default=3,
                     help="blocks repeated n-grams during generation (model default is 0 = off, "
                          "which lets it loop forever once uncertain)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=None, help="cap number of pages, for a quick smoke run")
    ap.add_argument("--full-res", action="store_true", help="skip the 600px-wide downscale used by the LLM pipeline")
    ap.add_argument("--4bit", dest="four_bit", action="store_true",
                     help="load weights in 4-bit (bitsandbytes) to free VRAM for crop_mode tiling")
    args = ap.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"

    doc_id, pages = load_pages(input_path, args.full_res)
    if args.limit:
        pages = pages[: args.limit]
    print(f"[{doc_id}] {len(pages)} page(s) loaded from {input_path}")

    print("Loading baidu/Unlimited-OCR ...")
    t_load = time.monotonic()
    tokenizer, model = load_model(four_bit=args.four_bit)
    print(f"Model loaded in {time.monotonic() - t_load:.1f}s")

    import torch

    with tempfile.TemporaryDirectory() as tmpdir:
        page_paths = []
        for i, page_bytes in enumerate(pages):
            p = Path(tmpdir) / f"page_{i + 1:03d}.jpg"
            p.write_bytes(page_bytes)
            page_paths.append(str(p))

        torch.cuda.reset_peak_memory_stats()
        t0 = time.monotonic()

        try:
            if args.multi and len(page_paths) > 1:
                text = run_multi(tokenizer, model, page_paths, args)
            else:
                chunks = []
                for i, p in enumerate(page_paths):
                    print(f"  page {i + 1}/{len(page_paths)} ...")
                    try:
                        chunks.append(run_page(tokenizer, model, p, args))
                    except torch.cuda.OutOfMemoryError:
                        print(f"  page {i + 1}: CUDA OOM — skipping (retry with --low-vram)")
                        torch.cuda.empty_cache()
                        chunks.append("")
                text = "\n\n".join(chunks)
        except torch.cuda.OutOfMemoryError:
            print("CUDA OOM on the whole run — retry with --low-vram or fewer pages (--limit).")
            sys.exit(1)

    latency_ms = round((time.monotonic() - t0) * 1000, 1)
    peak_vram_gb = round(torch.cuda.max_memory_allocated() / 1e9, 2)

    txt_path = out_dir / f"{doc_id}.txt"
    txt_path.write_text(text, encoding="utf-8")

    ratio = arabic_char_ratio(text)
    record = {
        "doc_id": doc_id,
        "page_count": len(pages),
        "latency_ms": latency_ms,
        "char_count": len(text),
        "arabic_char_ratio": ratio,
        "peak_vram_gb": peak_vram_gb,
        "args": {k: v for k, v in vars(args).items()},
    }

    existing = []
    if results_path.exists():
        existing = json.loads(results_path.read_text(encoding="utf-8"))
    existing.append(record)
    results_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[{doc_id}] {len(pages)} page(s), {latency_ms}ms, {len(text)} chars, "
          f"arabic_ratio={ratio}, peak_vram={peak_vram_gb}GB")
    print(f"Output: {txt_path}")
    print(f"First 200 chars:\n{text[:200]}")


if __name__ == "__main__":
    main()
