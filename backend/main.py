"""MathOCR FastAPI backend entry point."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import backend.config as config
from backend.db.database import init_db
from backend.routers import ocr, history, settings, auth, export, admin
from backend.llm.registry import list_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    _run_migrations()
    asyncio.create_task(_cleanup_temp_files())
    yield
    # Shutdown


def _run_migrations():
    """Add missing columns to existing databases (safe for fresh installs too)."""
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "data" / "mathocr.db"
    if not db_path.exists():
        db_path = Path("/data/mathocr.db")
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "is_admin" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            conn.commit()
        conn.close()
    except Exception:
        pass


app = FastAPI(
    title="MathOCR API",
    description="OCR math images and PDFs to LaTeX via configurable LLM backends",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(ocr.router)
app.include_router(history.router)
app.include_router(settings.router)
app.include_router(export.router)
app.include_router(admin.router)


@app.get("/api/providers")
async def get_providers() -> dict:
    """List all available LLM providers."""
    return {"providers": list_providers()}


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _cleanup_temp_files():
    """Periodically clean up old temp files (older than 1 hour)."""
    import time
    while True:
        try:
            import os
            from pathlib import Path
            cutoff = time.time() - 3600
            for p in config.TEMP_DIR.glob("*"):
                if p.is_file() and p.stat().st_mtime < cutoff:
                    try:
                        p.unlink()
                    except OSError:
                        pass
        except Exception:
            pass
        await asyncio.sleep(300)
