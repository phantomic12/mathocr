#!/usr/bin/env python3
"""
mathocr — OCR math images and PDFs to LaTeX using Qwen3.5-9B via FastFlowLM.

Usage:
    python mathocr.py <image_or_pdf> ...  Single or batch (auto-detects PDF)
    python mathocr.py <file> -o out.tex   Write LaTeX to file
    python mathocr.py --demo              Generate demo images and exit
    python mathocr.py --list-models        List available FLM models
    python mathocr.py --dpi 300            Set PDF rasterization DPI (default 200)
"""

import base64
import io
import json
import shutil
import subprocess
import sys
import tempfile
import argparse
from pathlib import Path

# ── setup ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
VENV_PY = ROOT / "bin" / "python"

# Detect venv python so the script works inside or outside the venv
try:
    import openai
except ImportError:
    # Fallback: use the venv python interpretter
    import subprocess, os
    venv_python = ROOT / "bin" / "python"
    os.execv(str(venv_python), [str(venv_python), __file__] + sys.argv)

# ── client ───────────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:52625/v1"
API_KEY   = "flm"
MODEL     = "qwen3.5:9b"

_client = None

def get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)
    return _client


# ── image helpers ─────────────────────────────────────────────────────────────
def load_image(path: str | Path) -> tuple[str, int, int]:
    """Load an image file and return (base64_str, width, height)."""
    try:
        from PIL import Image
    except ImportError:
        # PIL not available — try without resize info
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode(), 0, 0

    img = Image.open(path)
    w, h = img.size
    buf = io.BytesIO()
    fmt = img.format or "PNG"
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode(), w, h


def make_image_url(b64: str, fmt: str = "png") -> str:
    """Return a data-URI for the OpenAI vision API."""
    return f"data:image/{fmt};base64,{b64}"


# ── PDF support ──────────────────────────────────────────────────────────────
def pdf_to_images(pdf_path: str | Path, dpi: int = 200) -> list[Path]:
    """
    Convert a PDF to a list of PNG images using pdftoppm (Poppler).
    Returns list of Paths to the generated PNG files in a temp directory.
    Caller is responsible for cleaning up the temp directory.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Check for pdftoppm
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm (Poppler) not found — cannot process PDFs. "
                          "Install poppler-utils via your package manager.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="mathocr_pdf_"))
    base_out = tmp_dir / pdf_path.stem

    # -r: DPI, -png: output format
    # NOTE: without -singlefile, pdftoppm outputs {stem}-1.png, {stem}-2.png, ...
    # which is what we want for multi-page PDFs
    cmd = [pdftoppm, "-r", str(dpi), "-png", str(pdf_path), str(base_out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr}")

    # pdftoppm names files as {stem}-1.png, {stem}-2.png, etc.
    pages = sorted(tmp_dir.glob(f"{pdf_path.stem}-*.png"))
    return pages


# ── prompt ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are MathOCR, an expert at extracting mathematical content from images "
    "and converting it to clean, accessible LaTeX (or MathML when LaTeX is "
    "impractical).\n\n"
    "Rules:\n"
    "1. Output ONLY the raw LaTeX/MathML — no markdown fences, no explanation, "
    "no backticks, no code blocks.\n"
    "2. Prefer standard LaTeX commands (amsmath, amssymb) for best accessibility.\n"
    "3. For inline math use $...$, for display (block) math use $$...$$ or "
    "\\begin{align*}...\\end{align*}.\n"
    "4. Preserve all symbols exactly: Greek letters, integrals, summations, "
    "matrices, operators.\n"
    "5. If the image is NOT a math expression, return the plain text content.\n"
    "6. Handwritten or ambiguous symbols: use your best interpretation and "
    "note them briefly in a LaTeX comment %.\n"
    "7. For chemical equations use mhchem's \\ce{...} macro.\n"
)

USER_PROMPT = (
    "Convert the mathematical expression in this image to LaTeX. "
    "Output only the raw LaTeX code."
)


# ── core OCR function ────────────────────────────────────────────────────────
def ocr_image(image_path: str | Path) -> str:
    """
    Send a math image to Qwen3.5-9B and return LaTeX string.
    """
    client = get_client()
    b64_data, w, h = load_image(image_path)
    image_url = make_image_url(b64_data)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ],
        temperature=0.1,   # low randomness for reproducibility
        max_tokens=2048,
    )

    content = response.choices[0].message.content
    if content is None:
        return ""
    return content.strip()


def ocr_images(image_paths: list[str | Path]) -> list[tuple[Path, str]]:
    """
    Batch-process multiple images. Returns list of (Path, latex_str).
    Automatically handles PDFs by converting pages to images first.
    """
    results = []
    for p in image_paths:
        path = Path(p)
        latex = ocr_image(path)
        results.append((path, latex))
        print(f"  [OK] {path.name}")
    return results


def ocr_pdf(pdf_path: str | Path, dpi: int = 200) -> list[tuple[int, str]]:
    """
    Convert a PDF to page images and OCR each page.
    Returns list of (page_number, latex_str).
    Cleans up temp image directory after processing.
    """
    pdf_path = Path(pdf_path)
    print(f"  Converting PDF: {pdf_path.name} (DPI={dpi})")
    pages = pdf_to_images(pdf_path, dpi=dpi)
    print(f"  {len(pages)} page(s) extracted")

    results = []
    try:
        for i, page_img in enumerate(pages, start=1):
            latex = ocr_image(page_img)
            results.append((i, latex))
            print(f"  [OK] page {i}/{len(pages)}")
    finally:
        # Clean up temp images
        for p in pages:
            p.unlink(missing_ok=True)
        shutil.rmtree(pages[0].parent, ignore_errors=True)

    return results


# ── output ───────────────────────────────────────────────────────────────────
def print_latex(latex: str, source_name: str = "image"):
    print(f"\n{'='*60}")
    print(f"  LaTeX from: {source_name}")
    print(f"{'='*60}")
    print(latex)
    print(f"{'='*60}\n")


def print_pdf_results(results: list[tuple[int, str]], pdf_name: str):
    """Print OCR results for a multi-page PDF."""
    full_latex = []
    for page_num, latex in results:
        print(f"\n{'='*60}")
        print(f"  PDF: {pdf_name}  |  Page {page_num}")
        print(f"{'='*60}")
        print(latex)
        full_latex.append(latex)
    print(f"\n{'='*60}")
    print(f"  Total pages OCR'd: {len(results)}")
    print(f"{'='*60}\n")
    return "\n\n".join(full_latex)


def write_output(latex: str, output_path: Path):
    output_path.write_text(latex + "\n", encoding="utf-8")
    print(f"  -> Written to: {output_path}")


# ── demo: generate synthetic math test images ────────────────────────────────
def make_demo_images(out_dir: Path):
    """
    Create 5 synthetic math images using PIL for offline testing
    (no internet, no real OCR target).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL not available — skipping demo image generation.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    font_size = 28

    expressions = [
        ("01_integral.png",     r"∫₀^∞ e^{−x²} dx = √π / 2"),
        ("02_quadratic.png",    r"x = (−b ± √(b²−4ac)) / 2a"),
        ("03_matrix.png",       r"[1  2; 3  4] · [x; y] = [5; 6]"),
        ("04_series.png",       r"∑_{n=1}^∞ 1/n² = π²/6"),
        ("05_handwritten.png",  r"∂²u/∂t² = c² ∇²u"),
    ]

    # Try to use a monospace font; fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    for filename, text in expressions:
        W, H = 600, 80
        img = Image.new("RGB", (W, H), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (W - tw) // 2
        y = (H - th) // 2
        draw.text((x, y), text, fill=(0, 0, 0), font=font)
        img.save(out_dir / filename)
        print(f"  Created demo image: {out_dir / filename}")

    print(f"\nDemo images written to: {out_dir}/")
    print("Note: these are text-rendered images, not real handwritten math.")
    print("Use real photographed math images for OCR testing.\n")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Math OCR → LaTeX via Qwen3.5-9B (FastFlowLM)"
    )
    parser.add_argument(
        "images",
        nargs="*",
        default=[],
        help="Image file(s) to OCR. Omit to generate demo images.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file for single-image result.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate demo math images and exit.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available FastFlowLM models and exit.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="DPI for PDF rasterization (default: 200). Higher = slower but more accurate for small symbols.",
    )
    args = parser.parse_args()

    # ── list models ──────────────────────────────────────────────────────────
    if args.list_models:
        client = get_client()
        models = client.models.list()
        print("Available models:")
        for m in sorted(models.data, key=lambda x: x.id):
            print(f"  {m.id}")
        return

    # ── demo mode ─────────────────────────────────────────────────────────────
    if args.demo or (not args.images and not args.demo):
        demo_dir = ROOT / "demo_images"
        make_demo_images(demo_dir)
        if args.demo:
            return

    # ── batch OCR ─────────────────────────────────────────────────────────────
    if not args.images:
        print("No images provided. Run with --demo to generate test images.")
        print("Usage: python mathocr.py image1.png [image2.png ...]")
        return

    # Separate PDFs from images
    pdfs = [p for p in args.images if Path(p).suffix.lower() == ".pdf"]
    images = [p for p in args.images if Path(p).suffix.lower() != ".pdf"]

    # ── PDF processing ───────────────────────────────────────────────────────
    if pdfs:
        for pdf_path in pdfs:
            results = ocr_pdf(pdf_path, dpi=args.dpi)
            full = print_pdf_results(results, Path(pdf_path).name)
            if args.output:
                write_output(full, args.output)

    # ── image processing ─────────────────────────────────────────────────────
    if images:
        if len(images) == 1 and args.output:
            latex = ocr_image(images[0])
            print_latex(latex, images[0])
            write_output(latex, args.output)
        else:
            for path, latex in ocr_images(images):
                print_latex(latex, path.name)


if __name__ == "__main__":
    main()
