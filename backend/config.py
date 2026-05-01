"""Environment-driven settings for MathOCR backend."""
from pathlib import Path
import os


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).parent.parent
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR}/mathocr.db")

# ── Server ───────────────────────────────────────────────────────────────────
HOST: str = os.environ.get("HOST", "0.0.0.0")
PORT: int = int(os.environ.get("PORT", "8000"))
WORKERS: int = int(os.environ.get("WORKERS", "4"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "info")

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost,http://127.0.0.1,http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

# ── JWT / Auth ─────────────────────────────────────────────────────────────────
JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS: int = int(os.environ.get("JWT_EXPIRE_HOURS", "168"))  # 168h = 1 week

# ── Admin bootstrap ───────────────────────────────────────────────────────────
# If set, the first user to register with this email is auto-promoted to admin.
# Set these before starting the container for the first time.
ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")

# ── Upload settings ──────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB: int = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
TEMP_DIR: Path = Path(os.environ.get("TEMP_DIR", str(BASE_DIR / "tmp")))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Default provider ──────────────────────────────────────────────────────────
DEFAULT_PROVIDER: str = os.environ.get("DEFAULT_PROVIDER", "fastflowlm")

# ── Provider settings ─────────────────────────────────────────────────────────
# FastFlowLM (NPU)
FASTFLOWLM_BASE_URL: str = _get_env("FASTFLOWLM_BASE_URL", "http://127.0.0.1:52625/v1")
FASTFLOWLM_MODEL: str = _get_env("FASTFLOWLM_MODEL", "qwen3.5:9b")
FASTFLOWLM_API_KEY: str = _get_env("FASTFLOWLM_API_KEY", "flm")

# Ollama
OLLAMA_BASE_URL: str = _get_env("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL: str = _get_env("OLLAMA_MODEL", "qwen2.5vl:3b")
OLLAMA_API_KEY: str = _get_env("OLLAMA_API_KEY", "ollama")

# vLLM
VLLM_BASE_URL: str = _get_env("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
VLLM_MODEL: str = _get_env("VLLM_MODEL", "qwen2.5-7b-instruct")
VLLM_API_KEY: str = _get_env("VLLM_API_KEY", "token")

# OpenAI
OPENAI_API_KEY: str = _get_env("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = _get_env("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = _get_env("OPENAI_MODEL", "gpt-4o")

# Anthropic
ANTHROPIC_API_KEY: str = _get_env("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = _get_env("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

# LM Studio
LMSTUDIO_BASE_URL: str = _get_env("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LMSTUDIO_MODEL: str = _get_env("LMSTUDIO_MODEL", "")
LMSTUDIO_API_KEY: str = _get_env("LMSTUDIO_API_KEY", "lm-studio")

# Jan
JAN_BASE_URL: str = _get_env("JAN_BASE_URL", "http://127.0.0.1:1337/v1")
JAN_MODEL: str = _get_env("JAN_MODEL", "")
JAN_API_KEY: str = _get_env("JAN_API_KEY", "jan")

# LocalAI
LOCALAI_BASE_URL: str = _get_env("LOCALAI_BASE_URL", "http://127.0.0.1:8080/v1")
LOCALAI_MODEL: str = _get_env("LOCALAI_MODEL", "")
LOCALAI_API_KEY: str = _get_env("LOCALAI_API_KEY", "localai")

# Modal
MODAL_API_KEY: str = _get_env("MODAL_API_KEY", "")
MODAL_MODEL: str = _get_env("MODAL_MODEL", "")
