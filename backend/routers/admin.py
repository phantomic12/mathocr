"""Admin routes: user management."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse
from backend.db.database import get_session
from backend.db.models import User
from backend.routers.dependencies import get_current_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SetAdminRequest(BaseModel):
    user_id: str
    is_admin: bool


class DeleteUserRequest(BaseModel):
    user_id: str


@router.get("/users")
async def list_users(admin=Depends(get_current_admin_user)) -> JSONResponse:
    """List all users (admin only)."""
    with get_session() as session:
        users = session.query(User).order_by(User.created_at).all()
        return JSONResponse({"users": [u.to_dict() for u in users]})


@router.post("/users")
async def set_admin(body: SetAdminRequest, admin=Depends(get_current_admin_user)) -> JSONResponse:
    """Promote or demote a user to admin (admin only). Cannot modify yourself."""
    if body.user_id == admin.id:
        raise HTTPException(400, "Cannot modify your own admin status")

    with get_session() as session:
        user = session.query(User).filter(User.id == body.user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        user.is_admin = body.is_admin
        session.commit()
        return JSONResponse({"ok": True, "is_admin": user.is_admin})


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(get_current_admin_user)) -> JSONResponse:
    """Delete a user and all their jobs (admin only). Cannot delete yourself."""
    if user_id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")

    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        session.delete(user)
        session.commit()
        return JSONResponse({"ok": True})
