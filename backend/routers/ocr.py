"""OCR routes: upload, process, status, WebSocket."""
import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Depends
from starlette.responses import JSONResponse
import backend.config as config
from backend.db.database import get_session
from backend.db.models import Job, Setting, User
from backend.routers.dependencies import get_current_user
from backend.services.ocr_engine import process_job

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# Active WebSocket connections per job
_active_ws: dict[str, WebSocket] = {}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user: User = Depends(get_current_user)) -> JSONResponse:
    """Upload an image or PDF, create a job, return job_id."""
    # Validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large: {size_mb:.1f}MB > {config.MAX_FILE_SIZE_MB}MB")

    # Determine extension
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Save to temp storage
    job_id = str(uuid.uuid4())
    safe_name = f"{job_id}_{Path(filename).name}"
    dest = config.TEMP_DIR / safe_name
    with open(dest, "wb") as f:
        f.write(content)

    # Get current provider from settings
    provider_name = config.DEFAULT_PROVIDER
    with get_session() as session:
        row = session.query(Setting).filter(Setting.key == "active_provider").first()
        if row and row.value:
            provider_name = row.value

    # Determine page count (quick check for PDFs)
    file_type = "pdf" if ext == ".pdf" else "image"
    total_pages = 1

    # Create job record
    job = Job(
        id=job_id,
        filename=filename,
        file_path=str(dest),
        file_type=file_type,
        total_pages=total_pages,
        status="queued",
        provider=provider_name,
        user_id=user.id,
    )
    with get_session() as session:
        session.add(job)
        session.commit()

    # Start processing in background
    asyncio.create_task(_run_job(job_id, str(dest), filename, provider_name))

    return JSONResponse({
        "job_id": job_id,
        "filename": filename,
        "status": "queued",
    })


async def _run_job(job_id: str, file_path: str, filename: str, provider_name: str) -> None:
    """Background task to process a job."""
    ws = _active_ws.get(job_id)
    await process_job(job_id, file_path, filename, provider_name, ws)
    _active_ws.pop(job_id, None)


@router.websocket("/ws/{job_id}")
async def websocket_ocr(websocket: WebSocket, job_id: str) -> None:
    """WebSocket for streaming job progress."""
    await websocket.accept()
    _active_ws[job_id] = websocket
    try:
        # Keep connection alive and relay messages from process_job
        while True:
            data = await websocket.receive_text()
            # Client can send ping, we ignore
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _active_ws.pop(job_id, None)


@router.get("/status/{job_id}")
async def get_status(job_id: str, user: User = Depends(get_current_user)) -> JSONResponse:
    """Get job status and partial results."""
    with get_session() as session:
        job = session.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        return JSONResponse(job.to_dict())


@router.get("/result/{job_id}")
async def get_result(job_id: str, user: User = Depends(get_current_user)) -> JSONResponse:
    """Get full LaTeX result for a job."""
    with get_session() as session:
        job = session.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        if job.status == "error":
            raise HTTPException(500, job.result_error or "Processing failed")
        return JSONResponse({
            "job_id": job.id,
            "status": job.status,
            "latex": job.result_latex,
            "page_results": job.page_results,
            "filename": job.filename,
            "process_time_ms": job.process_time_ms,
        })
