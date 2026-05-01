"""OCR engine: orchestrates PDF→images→LLM processing with WebSocket progress."""
import asyncio
import base64
import io
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional
from fastapi import WebSocket

from backend.llm.registry import get_provider
from backend.llm.routing import select_provider
from backend.routers.settings import _get_routing_config
from backend.db.database import get_session
from backend.db.models import Job
from backend.services.pdf_utils import pdf_to_images
from backend.services.latex_cleaner import clean_latex
import backend.config as config

# System prompt instructing the model to return ONLY LaTeX
SYSTEM_PROMPT = (
    "You are an expert at transcribing mathematical handwriting or print into clean LaTeX. "
    "Return ONLY the LaTeX code — no explanation, no markdown fences, no comments. "
    "For display math use \\[ ... \\] or $$ ... $$. For inline math use $ ... $."
)


def _load_image_b64(path: Path) -> tuple[str, str]:
    """Load image as base64 and return (data_uri, mime_type)."""
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return f"data:image/jpeg;base64,{b64}", "image/jpeg"
    return f"data:image/png;base64,{b64}", "image/png"


def _detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    return "image"


async def process_job(
    job_id: str,
    file_path: str,
    filename: str,
    provider_name: str,
    websocket: Optional[WebSocket] = None,
) -> None:
    """Process a job: convert PDF if needed, call LLM per page, stream tokens."""
    start_time = time.time()
    routing = _get_routing_config()
    mode = routing.get("mode", "single")
    if mode == "single":
        # Legacy single-provider mode
        provider = get_provider(provider_name)
        if provider is None:
            provider = get_provider(config.DEFAULT_PROVIDER)
        if provider is None:
            raise ValueError(f"No LLM provider available: {provider_name}")
    else:
        # Load balanced: determine enabled providers and weights
        enabled = routing.get("enabled", {})
        weights = routing.get("weights", {})
        all_provider_names = [p[0] for p in enabled.items() if p[1]] if enabled else [provider_name]
        enabled_providers = [
            (name, weights.get(name, 1.0))
            for name in all_provider_names
            if enabled.get(name, True)
        ]
        if not enabled_providers:
            enabled_providers = [(provider_name, 1.0)]
        provider_name = select_provider("ocr", enabled_providers)
        provider = get_provider(provider_name)
        if provider is None:
            raise ValueError(f"No LLM provider available: {provider_name}")

    file_type = _detect_file_type(filename)
    image_paths: list[Path] = []
    tmp_dir: Optional[Path] = None

    # Thread-safe queue for token updates from the streaming thread
    token_queue: asyncio.Queue = asyncio.Queue()
    # Mutable flag so on_token_chunk (sync func) can signal the pump
    _streaming = {"done": False}

    async def send_json(data: dict):
        if websocket:
            try:
                await websocket.send_json(data)
            except Exception:
                pass  # Client disconnected

    async def pump_queue():
        """Pump token updates from queue to WebSocket as they arrive."""
        while not _streaming["done"]:
            try:
                data = await asyncio.wait_for(token_queue.get(), timeout=0.05)
                await send_json(data)
            except asyncio.TimeoutError:
                continue
        # Drain any remaining items
        while not token_queue.empty():
            try:
                data = token_queue.get_nowait()
                await send_json(data)
            except asyncio.QueueEmpty:
                break

    def on_token_chunk(accumulated: str, usage: Optional[dict]):
        if usage:
            tok_per_sec = usage.get("tok_per_sec", 0)
            tok_count = usage.get("completion_tokens", 0)
            elapsed_ms = int((time.time() - start_time) * 1000)
            try:
                token_queue.put_nowait({
                    "type": "token_progress",
                    "job_id": job_id,
                    "tokens": tok_count,
                    "tok_per_sec": tok_per_sec,
                    "chars": len(accumulated),
                    "elapsed_ms": elapsed_ms,
                })
            except Exception:
                pass  # Queue full — skip

    try:
        # Convert PDF to images if needed
        if file_type == "pdf":
            tmp_dir = Path(file_path).parent
            images = pdf_to_images(file_path, dpi=200)
            image_paths = images
        else:
            image_paths = [Path(file_path)]

        total_pages = len(image_paths)
        page_results = []

        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.total_pages = total_pages
                job.status = "processing"
                session.commit()

        # Process each page
        for page_idx, img_path in enumerate(image_paths):
            data_uri, _ = _load_image_b64(img_path)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe this math content to LaTeX:"},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ]

            # Start queue pump task — runs concurrently with streaming
            _streaming["done"] = False
            pump = asyncio.create_task(pump_queue())

            try:
                raw = provider.stream_complete(messages, on_token_chunk)
                latex = clean_latex(raw)
            except Exception as e:
                latex = f"<!-- OCR ERROR: {e} -->"

            # Signal pump to drain remaining items and stop
            _streaming["done"] = True
            await pump

            page_results.append(latex)

            # Notify WebSocket client — page is done
            await send_json({
                "type": "page_progress",
                "job_id": job_id,
                "page": page_idx + 1,
                "total_pages": total_pages,
                "latex": latex,
            })

            # Update job progress in DB
            with get_session() as session:
                job = session.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.page_results = page_results.copy()
                    session.commit()

        # Mark done
        elapsed_ms = int((time.time() - start_time) * 1000)
        full_latex = "\n\n".join(page_results)

        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "done"
                job.result_latex = full_latex
                job.page_results = page_results
                job.process_time_ms = elapsed_ms
                session.commit()

        await send_json({
            "type": "done",
            "job_id": job_id,
            "latex": full_latex,
            "process_time_ms": elapsed_ms,
        })

    except Exception as e:
        _streaming["done"] = True
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "error"
                job.result_error = str(e)
                session.commit()

        await send_json({
            "type": "error",
            "job_id": job_id,
            "error": str(e),
        })


