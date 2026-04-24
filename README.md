# MathOCR

**Turn math images and PDFs into accessible LaTeX — powered by Qwen3.5-9B via FastFlowLM.**

```
$ mathocr.py exam.pdf
[OK] exam-01.png
============================================================
============================================================
\begin{enumerate}
    \item In right triangle $JOE$, hypotenuse $JO = 31.8$ ...
...
```

## What it does

- **Single image** → LaTeX (`mathocr.py photo.jpg`)
- **PDF** → page images → LaTeX per page (`mathocr.py exam.pdf`)
- Batch processing with per-page JSON results and combined `.tex` output
- Raw LaTeX output (no fences, no markdown) ready for accessibility tools

## Requirements

- **FastFlowLM** running locally with `qwen3.5:9b` loaded
  - Default URL: `http://127.0.0.1:52625/v1`
  - API key: `flm`
- **Python 3.11+** with `openai`, `Pillow`, `pypdf` (or `pymupdf` for faster PDF rendering)
- **poppler-utils** (`pdftoppm`) for PDF rasterization

## Quick start

```bash
# 1. Install dependencies
pip install openai Pillow pypdf

# 2. Start FastFlowLM with qwen3.5:9b (example)
fastflowlm run qwen3.5:9b --port 52625

# 3. Run OCR
python mathocr.py math_photo.png
python mathocr.py exam.pdf -o output.tex

# 4. Or use the venv
./bin/python mathocr.py math_photo.png
```

## File overview

| File | Purpose |
|------|---------|
| `mathocr.py` | Main CLI — single image or PDF. Run with `-o out.tex` to save output. |
| `batch_process.py` | Process a full exam PDF: extract pages → OCR each → save per-page JSON + combined `.tex` |
| `rerun_failed.py` | Re-OCR only pages that timed out (fixes timeout + re-runs at higher limit) |

## Usage examples

### Single image
```bash
python mathocr.py equation.png
python mathocr.py equation.png -o equation.tex
```

### Full PDF exam
```bash
python batch_process.py geom-final.pdf
# Output: geom-final/geom-final_p01.json ... geom-final/geom-final_pNN.json
#         geom-final/geom-final_full.tex
```

### Re-run timed-out pages
```bash
# Edit FAILED_* lists in rerun_failed.py, then:
python rerun_failed.py
```

## Output format

`mathocr.py` prints:

```
[OK] filename.png
============================================================
============================================================
\begin{enumerate}
    \item ...
    \item ...
\end{enumerate}
============================================================
```

The LaTeX (between the 2nd and last `===` lines) is **raw LaTeX** — no markdown fences, no backticks. Suitable for:

- Pasting into LaTeX documents directly
- Converting to MathML / accessible HTML via `tex4ht`, `MathJax`, or `MathLive`
- Feeding into braille translation pipelines
- Screen reader access via NVDA/JAWS with MathPlayer

## LLM configuration

`mathocr.py` connects to FastFlowLM at `http://127.0.0.1:52625/v1`. To change the URL or model, edit these lines in `mathocr.py`:

```python
BASE_URL = "http://127.0.0.1:52625/v1"
API_KEY  = "flm"           # your FastFlowLM API key
MODEL    = "qwen3.5:9b"    # model name
```

For **Ollama**, change `BASE_URL` to `http://127.0.0.1:11434/v1` and use the Ollama model name (e.g. `"llama3.2-vision"`).

For **lmstudio**, change `BASE_URL` to `http://127.0.0.1:1234/v1`.

## System requirements

- ~8GB RAM for Qwen3.5-9B in FP16
- FastFlowLM AMD NPU acceleration (optional; runs on CPU/MGPU if unavailable)
- 200 DPI PDF rasterization; raise to `300` or `400` for dense small-print exams

## Performance

Qwen3.5-9B timing on a scanned geometry exam (~A4, 2-column, 12pt font):

| Page type | Time |
|-----------|------|
| Cover / title page | 30–60s |
| Simple content (few equations) | 60–120s |
| Dense content (many problems, 2-column) | 120–300s |

Set `timeout=600` in `batch_process.py` / `rerun_failed.py` for safety on dense pages.

## Architecture

```
mathocr.py
├── ocr_image()          — send base64 image to FastFlowLM chat completions API
├── load_image()         — base64-encode PNG/JPG, optionally resize
├── pdf_to_images()      — pdftoppm → temp PNGs
├── ocr_pdf()            — convert PDF → page images → OCR each → cleanup
└── print_latex()       — format output with === delimiters

batch_process.py
├── extract_latex_from_stdout()  — parse LaTeX from mathocr.py stdout
├── process_exam()               — run full exam: pages → OCR → JSON + .tex
└── main()                       — dispatch both exams
```

## License

MIT
