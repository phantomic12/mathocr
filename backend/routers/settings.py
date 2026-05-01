"""Settings routes: provider configuration and routing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
from backend.db.database import get_session
from backend.db.models import Setting
from backend.llm.registry import list_providers, get_provider
from backend.routers.dependencies import get_current_admin_user
import backend.config as config

router = APIRouter(prefix="/api/settings", tags=["settings"])


class RoutingConfigUpdate(BaseModel):
    mode: str | None = None  # "single" | "weighted" | "round_robin"
    enabled: dict[str, bool] | None = None  # {provider_name: bool}
    weights: dict[str, float] | None = None  # {provider_name: weight}


def _upsert_setting(session, key: str, value: str) -> Setting:
    row = session.query(Setting).filter(Setting.key == key).first()
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    return row


def _get_routing_config() -> dict:
    with get_session() as session:
        row = session.query(Setting).filter(Setting.key == "routing_config").first()
        if row and row.value:
            import json
            return json.loads(row.value)
    return {"mode": "single", "enabled": {}, "weights": {}}


def _save_routing_config(cfg: dict) -> None:
    import json
    with get_session() as session:
        _upsert_setting(session, "routing_config", json.dumps(cfg))
        session.commit()


@router.get("")
async def get_settings() -> JSONResponse:
    """Get active provider, routing config, and all provider metadata."""
    providers = list_providers()

    # Ping each provider to get online status
    provider_status = {}
    for p in providers:
        name = p["name"]
        prov = get_provider(name)
        online = prov is None or _ping_provider(prov)
        provider_status[name] = {"online": online}

    with get_session() as session:
        rows = session.query(Setting).all()
        settings = {r.key: r.value for r in rows}
        active = settings.get("active_provider", config.DEFAULT_PROVIDER)

    routing = _get_routing_config()

    # Merge defaults: fill in any provider not yet in config
    all_provider_names = [p["name"] for p in providers]
    if not routing.get("enabled"):
        routing["enabled"] = {n: True for n in all_provider_names}
    else:
        for n in all_provider_names:
            routing["enabled"].setdefault(n, True)
    if not routing.get("weights"):
        routing["weights"] = {n: 1.0 for n in all_provider_names}
    else:
        for n in all_provider_names:
            routing["weights"].setdefault(n, 1.0)

    return JSONResponse({
        "active_provider": active,
        "routing": routing,
        "providers": providers,
        "provider_status": provider_status,
        "settings": settings,
    })


def _ping_provider(prov) -> bool:
    """Quick liveness check — call /models or equivalent, return False on failure."""
    try:
        # Most OpenAI-compatible providers respond to /models
        import httpx, asyncio
        url = getattr(prov, "base_url", None)
        if url:
            # sync check for simplicity
            import urllib.request
            req = urllib.request.Request(f"{url.rstrip('/')}/models", method="GET")
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    return resp.status == 200
            except Exception:
                return False
        return True
    except Exception:
        return False


@router.put("")
async def update_settings(
    active_provider: str | None = None,
    admin=Depends(get_current_admin_user),
) -> JSONResponse:
    """Update active provider (admin only)."""
    if active_provider is None:
        raise HTTPException(400, "Nothing to update")
    with get_session() as session:
        _upsert_setting(session, "active_provider", active_provider)
        session.commit()
    return JSONResponse({"ok": True})


@router.get("/routing")
async def get_routing() -> JSONResponse:
    """Get current routing configuration."""
    providers = list_providers()
    all_provider_names = [p["name"] for p in providers]

    routing = _get_routing_config()

    # Merge defaults so UI always has all providers
    routing.setdefault("enabled", {})
    routing.setdefault("weights", {})
    for n in all_provider_names:
        routing["enabled"].setdefault(n, True)
        routing["weights"].setdefault(n, 1.0)

    # Build providers list (matches the /api/settings response shape)
    provider_status = {}
    for p in providers:
        name = p["name"]
        prov = get_provider(name)
        online = prov is None or _ping_provider(prov)
        provider_status[name] = {"online": online}

    return JSONResponse({
        "mode": routing.get("mode", "single"),
        "providers": {
            n: {
                "enabled": routing["enabled"].get(n, True),
                "weight": routing["weights"].get(n, 1.0),
            }
            for n in all_provider_names
        },
        "provider_status": provider_status,
    })


@router.put("/routing")
async def update_routing(
    data: RoutingConfigUpdate,
    admin=Depends(get_current_admin_user),
) -> JSONResponse:
    """Update routing configuration (admin only)."""
    cfg = _get_routing_config()
    if data.mode is not None:
        cfg["mode"] = data.mode
    if data.enabled is not None:
        cfg["enabled"] = data.enabled
    if data.weights is not None:
        cfg["weights"] = data.weights
    _save_routing_config(cfg)
    return JSONResponse({"ok": True, "routing": cfg})
