"""History routes: CRUD for past jobs."""
from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from backend.db.database import get_session
from backend.db.models import Job, User
from backend.routers.dependencies import get_current_user

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def list_history(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """List past jobs for the current user, most recent first."""
    offset = (page - 1) * per_page
    with get_session() as session:
        query = session.query(Job).filter(Job.user_id == user.id)
        total = query.count()
        jobs = (
            query
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return JSONResponse({
            "items": [j.to_dict() for j in jobs],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })


@router.get("/{job_id}")
async def get_history_job(job_id: str, user: User = Depends(get_current_user)) -> JSONResponse:
    """Get a specific job by ID."""
    with get_session() as session:
        job = session.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        return JSONResponse(job.to_dict())


@router.delete("/{job_id}")
async def delete_history_job(job_id: str, user: User = Depends(get_current_user)) -> JSONResponse:
    """Delete a job and its temp file."""
    with get_session() as session:
        job = session.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            raise HTTPException(404, "Job not found")
        file_path = job.file_path
        session.delete(job)
        session.commit()

    # Remove temp file
    from pathlib import Path
    p = Path(file_path)
    if p.exists():
        p.unlink()

    return JSONResponse({"ok": True})
