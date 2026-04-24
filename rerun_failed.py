#!/usr/bin/env python3
"""Re-run OCR on pages that timed out with the old 300s limit."""
import json, subprocess, time
from pathlib import Path

PY     = Path("/home/yoav/projects/mathocr/bin/python")
SCRIPT = Path("/home/yoav/projects/mathocr/mathocr.py")
BASE   = Path("/home/yoav/projects/mathocr/exam_results")

# Cached page images from the original batch runs
IMG_DIR_82025 = Path("/tmp/mathocr_batch_458tatft")
IMG_DIR_12026 = Path("/tmp/mathocr_batch_ldnsj6bk")

# Pages that returned [EMPTY] (old extraction bug) — need full re-OCR
FAILED_82025 = [2, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 27, 28]
FAILED_12026 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 27, 28]


def extract_latex(stdout: str) -> str:
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


def run_page(img_path: Path, exam_stem: str, page_num: int):
    """Write to {stem}_p{page:02d}.json  (e.g. geom-82025-exam_p02.json)"""
    out_json = BASE / exam_stem / f"{exam_stem}_p{page_num:02d}.json"
    start = time.time()
    try:
        r = subprocess.run(
            [str(PY), str(SCRIPT), str(img_path)],
            capture_output=True, text=True, timeout=600
        )
        if r.returncode != 0:
            latex = f"[ERROR: {r.stderr.strip()}]"
        else:
            latex = extract_latex(r.stdout)
            if not latex:
                latex = "[EMPTY]"
    except subprocess.TimeoutExpired:
        latex = "[TIMEOUT]"

    elapsed = time.time() - start
    result = {"page": page_num, "latex": latex}
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  p{page_num:02d} ({elapsed:.0f}s) [{len(latex)} chars] -> {out_json.name}")
    return result


def main():
    pages = (
        [(IMG_DIR_82025 / f"geom-82025-exam-{p:02d}.png",
          "geom-82025-exam", p)
         for p in FAILED_82025]
        +
        [(IMG_DIR_12026 / f"geom-12026-exam-{p:02d}.png",
          "geom-12026-exam", p)
         for p in FAILED_12026]
    )
    print(f"Re-processing {len(pages)} pages @ 600s timeout …")
    t0 = time.time()
    for i, (img, exam, p) in enumerate(pages, 1):
        print(f"[{i:02d}/{len(pages)}] ", end="", flush=True)
        run_page(img, exam, p)
    print(f"\nDone in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
