"""Settings routes: provider configuration."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
from backend.db.database import get_session
from backend.db.models import Setting
from backend.llm.registry import list_providers
from backend.routers.dependencies import get_current_admin_user
import backend.config as config

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    active_provider: str | None = None


@router.get("")
async def get_settings() -> JSONResponse:
    """Get all settings including active provider."""
    with get_session() as session:
        rows = session.query(Setting).all()
        settings = {r.key: r.value for r in rows}
        active = settings.get("active_provider", config.DEFAULT_PROVIDER)
        return JSONResponse({
            "active_provider": active,
            "providers": list_providers(),
            "settings": settings,
        })


def _upsert_setting(session, key: str, value: str) -> Setting:
    row = session.query(Setting).filter(Setting.key == key).first()
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    return row


@router.put("")
async def update_settings(data: SettingsUpdate, admin = Depends(get_current_admin_user)) -> JSONResponse:
    """Update settings (e.g., switch active provider)."""
    with get_session() as session:
        if data.active_provider is not None:
            _upsert_setting(session, "active_provider", data.active_provider)
        session.commit()
        return JSONResponse({"ok": True})
