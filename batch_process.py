#!/usr/bin/env python3
"""
Batch-process Geometry exam PDFs and save OCR results.
Saves: exam_results/{stem}/{stem}_p{page:02d}.json  (per page)
       exam_results/{stem}/{stem}_full.tex           (combined)
       exam_results/{stem}/summary.json              (stats)
"""
import json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

# ── paths ───────────────────────────────────────────────────────────────────
PY     = Path("/home/yoav/projects/mathocr/bin/python")
SCRIPT = Path("/home/yoav/projects/mathocr/mathocr.py")
BASE   = Path("/home/yoav/projects/mathocr/exam_results")

PDFS = [
    "/home/yoav/projects/mathocr/geom-82025-exam.pdf",
    "/home/yoav/projects/mathocr/geom-12026-exam.pdf",
]

DPI = 200


def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr}")
    return r.stdout


def pdf_page_count(pdf_path):
    out = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True
    )
    for line in out.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    raise RuntimeError(f"Could not determine page count for {pdf_path}")


def extract_latex_from_stdout(stdout: str) -> str:
    """
    Parse LaTeX from mathocr.py CLI output.

    mathocr.py prints a ===-delimited header block, then the LaTeX, then a
    trailing === delimiter:

        [OK] file.png
        ============================================================
          LaTeX from: file.png
        ============================================================
        \begin{enumerate}          <-- actual LaTeX starts here
        ...
        \end{enumerate}
        ============================================================

    The actual content lives between the 2nd === line and the last === line.
    """
    lines = stdout.splitlines()
    eq_indices = [i for i, ln in enumerate(lines)
                  if ln.strip().startswith("=") and ln.strip("=").strip() == ""]
    if len(eq_indices) < 2:
        return ""
    # Content between 2nd === and last ===
    inner_lines = lines[eq_indices[1] + 1: eq_indices[-1]]
    content = "\n".join(inner_lines).strip()
    if content.startswith(r"\documentclass") or \
       content.startswith(r"\begin{document}"):
        return ""
    return content


def process_pdf(pdf_path: Path):
    stem = pdf_path.stem
    out_dir = BASE / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    n_pages = pdf_page_count(pdf_path)
    print(f"[{stem}] {n_pages} pages to process")

    # Extract all pages to a temp dir
    tmp_dir = Path(tempfile.mkdtemp(prefix="mathocr_batch_"))
    base_out = tmp_dir / stem
    run(["pdftoppm", "-r", str(DPI), "-png", str(pdf_path), str(base_out)])
    pages = sorted(tmp_dir.glob(f"{stem}-*.png"))
    assert len(pages) == n_pages, f"Expected {n_pages} pages, got {len(pages)}"

    results = []
    total_errors = 0

    for i, page_img in enumerate(pages, start=1):
        page_num = i
        print(f"[{stem}] Page {page_num}/{n_pages}...", flush=True)

        try:
            r = subprocess.run(
                [str(PY), str(SCRIPT), str(page_img)],
                capture_output=True, text=True, timeout=600
            )
            if r.returncode != 0:
                latex = f"[ERROR: {r.stderr.strip()}]"
                total_errors += 1
            else:
                latex = extract_latex_from_stdout(r.stdout)
                if not latex:
                    latex = "[EMPTY]"
        except subprocess.TimeoutExpired:
            latex = "[TIMEOUT]"
            total_errors += 1

        result = {"page": page_num, "latex": latex}
        results.append(result)

        # Save per-page JSON
        page_json = out_dir / f"{stem}_p{page_num:02d}.json"
        page_json.write_text(json.dumps(result, indent=2), encoding="utf-8")

        # Append to combined .tex
        tex_file = out_dir / f"{stem}_full.tex"
        with open(tex_file, "a", encoding="utf-8") as f:
            f.write(f"% ── Page {page_num} ─────────────────────────────────────────────\n")
            f.write(latex + "\n\n")

    # Save summary
    summary = {
        "pdf": str(pdf_path),
        "total_pages": n_pages,
        "errors": total_errors,
        "pages": [
            {
                "page": r["page"],
                "has_content": bool(
                    r["latex"]
                    and r["latex"] not in ("[TIMEOUT]", "[EMPTY]")
                    and "[ERROR" not in r["latex"]
                ),
            }
            for r in results
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Cleanup temp images
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"[{stem}] DONE — {n_pages} pages, {total_errors} errors → {out_dir}")


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    total_start = time.time()

    for pdf in PDFS:
        pdf_path = Path(pdf)
        start = time.time()
        try:
            process_pdf(pdf_path)
        except Exception as e:
            print(f"[{pdf_path.stem}] FAILED: {e}")
        elapsed = time.time() - start
        print(f"[{pdf_path.stem}] Elapsed: {elapsed:.1f}s")

    total_elapsed = time.time() - total_start
    print(f"\nTotal elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
