"""
Pre-warm OCR models at worker startup.
Each engine is loaded in a subprocess so a segfault in one doesn't kill the container.
Models are cached in named Docker volumes so downloads only happen on first run.
"""
import subprocess
import sys

def _preload(name: str, code: str) -> None:
    print(f"[preload] Initializing {name}...", flush=True)
    result = subprocess.run([sys.executable, "-c", code], timeout=600)
    if result.returncode == 0:
        print(f"[preload] {name} ready.", flush=True)
    else:
        print(
            f"[preload] {name} exited with code {result.returncode} — "
            "will lazy-load on first task (non-fatal).",
            flush=True,
        )

print("[preload] Starting OCR model warm-up...", flush=True)

_preload(
    "EasyOCR",
    "import easyocr; easyocr.Reader(['ar', 'en'], gpu=False, verbose=False)",
)

_preload(
    "PaddleOCR",
    "from paddleocr import PaddleOCR; PaddleOCR(lang='ar', use_angle_cls=True, show_log=False)",
)

print("[preload] Model warm-up complete.", flush=True)
