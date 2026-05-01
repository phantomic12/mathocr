"""PDF to image conversion using pdftoppm."""
import shutil
import subprocess
import tempfile
from pathlib import Path


def pdf_to_images(pdf_path: str | Path, dpi: int = 200) -> list[Path]:
    """Convert PDF pages to PNG images. Returns sorted list of image paths."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError(
            "pdftoppm (Poppler) not found. Install poppler-utils via your package manager."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="mathocr_pdf_"))
    base_out = tmp_dir / pdf_path.stem

    cmd = [pdftoppm, "-r", str(dpi), "-png", str(pdf_path), str(base_out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr}")

    images = sorted(tmp_dir.glob("*.png"))
    return images
