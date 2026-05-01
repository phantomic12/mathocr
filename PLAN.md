# MathOCR Web UI — Implementation Plan

## Goal

Build a self-hosted, locally-deployable MathOCR web application that:
1. Accepts images and PDFs via drag-and-drop
2. Sends them to a configurable LLM backend (Qwen3.5-VL via FastFlowLM, Ollama, vLLM, OpenAI, Anthropic, LM Studio, Jan, LocalAI, Modal, etc.)
3. Returns accessible LaTeX rendered as math
4. Supports batch processing, history, and multi-provider switching
5. Exports results to DOCX, PDF, and EPUB with accessible math markup

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Web Browser                         │
│               React SPA (Vite, no framework)            │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  OCR Routes  │  │  LLM Bridge  │  │  History/   │  │
│  │  (upload,    │  │  (unified    │  │  Settings   │  │
│  │   process)   │  │   provider    │  │  (SQLite)   │  │
│  │              │  │   interface)  │  │             │  │
│  └──────────────┘  └──────────────┘  └─────────────┘  │
└────────┬───────────────┬───────────────┬────────────────┘
         │               │               │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐
    │FastFlowLM│   │ Ollama /  │  │ OpenAI  │
    │(Qwen3.5) │   │ vLLM /    │  │Anthropic │
    │  NPU     │   │ LM Studio │  │ LM Studio│
    └──────────┘   └───────────┘  └──────────┘
```

---

## Tech Stack

| Layer      | Choice                                           |
|------------|--------------------------------------------------|
| Frontend   | Vanilla JS + Vite (no heavy framework)           |
| Backend    | FastAPI (Python 3.11+)                           |
| Database   | SQLite via SQLAlchemy (history, settings)        |
| File queue | In-process (no Redis needed for single-user)     |
| LLM layer  | `openai` Python client (unified across providers)|
| PDF→IMG    | `pdftoppm` (pre-installed, no Python dep)        |
| Math render| KaTeX (client-side, CDN)                         |
| Deploy     | Docker + Docker Compose                          |
| Accessibility | JAWS/NVDA-compatible — skip links, ARIA roles and live regions, keyboard-navigable, semantic HTML, visible focus styles |
| Export     | DOCX (python-docx), PDF (WeasyPrint HTML→PDF), EPUB3 (zip of XHTML) |
| Auth       | User accounts (email/password, JWT) + Admin accounts (change settings, manage users) |

---

## File Structure

```
mathocr-web/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings from env
│   ├── routers/
│   │   ├── ocr.py             # Upload, process, status endpoints
│   │   ├── history.py         # Job history CRUD
│   │   └── settings.py        # Provider config
│   ├── llm/
│   │   ├── base.py            # Abstract LLMProvider
│   │   ├── fastflowlm.py      # FastFlowLM adapter
│   │   ├── ollama.py          # Ollama adapter
│   │   ├── vllm.py            # vLLM adapter
│   │   ├── openai.py          # OpenAI-compatible adapter
│   │   ├── anthropic.py       # Anthropic adapter
│   │   ├── lmstudio.py        # LM Studio adapter
│   │   ├── jan.py             # Jan adapter
│   │   ├── localai.py         # LocalAI adapter
│   │   └── registry.py        # Provider registry + discovery
│   ├── services/
│   │   ├── ocr_engine.py      # Orchestrates PDF→IMG→LLM
│   │   ├── pdf_utils.py       # pdftoppm wrapper
│   │   └── latex_cleaner.py   # Post-process / normalize LaTeX
│   └── db/
│       ├── models.py           # SQLAlchemy models
│       └── database.py        # Session management
├── frontend/
│   ├── index.html
│   ├── main.js
│   ├── style.css
│   └── components/
│       ├── DropZone.js
│       ├── ResultPanel.js
│       ├── HistoryPanel.js
│       ├── ProviderSelector.js
│       └── RenderedMath.js
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## LLM Provider Interface (abstraction)

Every provider implements:

```python
class LLMProvider(ABC):
    name: str
    supports_images: bool = True

    @abstractmethod
    def complete(self, messages: list[dict], **kwargs) -> str:
        """Returns raw text response from model."""

    @abstractmethod
    def get_model_id(self) -> str:
        """Returns the model string to use in API calls."""
```

Provider selection is runtime-configured via SQLite settings table.

---

## API Endpoints

| Method | Path                        | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | `/api/ocr/upload`           | Upload image/PDF, returns job_id   |
| GET    | `/api/ocr/status/{job_id}`  | Poll job status + partial results  |
| GET    | `/api/ocr/result/{job_id}`  | Fetch full LaTeX result           |
| GET    | `/api/history`              | List past jobs (paginated)         |
| DELETE | `/api/history/{job_id}`     | Delete a job                      |
| POST   | `/api/ocr/export/docx/{job_id}` | Export job result as DOCX  |
| POST   | `/api/ocr/export/pdf/{job_id}`  | Export job result as PDF   |
| POST   | `/api/ocr/export/epub/{job_id}` | Export job result as EPUB  |
| GET    | `/api/admin/users`            | List all users (admin only) |
| POST   | `/api/admin/users`            | Promote/demote user to admin (admin only) |
| DELETE | `/api/admin/users/{user_id}`  | Delete a user (admin only) |
| GET    | `/api/providers`            | List available providers           |
| GET    | `/api/settings`             | Get current provider config        |
| PUT    | `/api/settings`             | Update provider config            |

WebSocket: `/ws/ocr/{job_id}` — stream progress updates (page N/N done)

---

## Web UI Flow

1. User opens app → selects provider from dropdown (or uses default)
2. Drags image/PDF onto drop zone (or clicks to browse)
3. Backend confirms job created → UI shows job card with spinner
4. Backend processes (PDF→pages→LLM) → WebSocket pushes page progress
5. Each page result streams in → KaTeX renders inline preview
6. Full result available → copy-to-clipboard, download .tex, download PDF
7. History sidebar shows all past jobs with instant reload

---

## Batch Processing (server-side)

- Upload creates a **Job** record (status: `queued`)
- Worker iterates pages: for each page, calls `llm.complete()`
- Results stored in SQLite as they complete (partial results available)
- Job status: `queued` → `processing` → `done` | `error`

---

## Provider Configuration (env vars + DB)

Each provider reads from env or DB:

```
# FastFlowLM (NPU)
FASTFLOWLM_BASE_URL=http://127.0.0.1:52625/v1
FASTFLOWLM_MODEL=qwen3.5:9b

# Ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=qwen2.5vl:3b

# vLLM
VLLM_BASE_URL=http://127.0.0.1:8000/v1
VLLM_MODEL=qwen2.5-7b-instruct

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# LM Studio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=... (model name from /models list)

# Jan
JAN_BASE_URL=http://127.0.0.1:1337/v1
JAN_MODEL=...

# LocalAI
LOCALAI_BASE_URL=http://127.0.0.1:8080/v1
LOCALAI_MODEL=...
```

---

## Docker Compose Design

Single compose file with **profiles**:

```yaml
services:
  mathocr-backend:
    build: ./backend
    profiles: [backend]        # runs without UI (API-only)
    env_file: .env
    volumes:
      - ./data:/app/data       # SQLite DB
    depends_on:
      - fastflowlm             # if using NPU

  fastflowlm:
    image: fastflowlm/fastflowlm:latest
    profiles: [npu]            # only on AMD NPU hardware
    device: /dev/dri:/dev/dri  # NPU passthrough
    ports: ["52625:52625"]

  ollama:
    image: ollama/ollama:latest
    profiles: [ollama]
    ports: ["11434:11434"]
    volumes: ollama-data:/root/.ollama

  vllm:
    image: vllm/vllm:latest
    profiles: [vllm]
    ports: ["8000:8000"]
    command: --model Qwen/Qwen2.5-7B-Instruct ...

  mathocr-frontend:
    build: ./frontend
    profiles: [frontend]
    ports: ["3000:80"]
    depends_on: [mathocr-backend]

  mathocr-app:
    profiles: [full]           # everything including UI
    build:
      context: .
      dockerfile: Dockerfile.allinone
    env_file: .env
    ports: ["3000:3000", "52625:52625"]
    volumes:
      - ./data:/app/data
    device: /dev/dri:/dev/dri   # NPU
```

### Deployment Profiles

```bash
# Full local (FastFlowLM NPU + backend + web UI)
/opt/mathocr docker compose --profile full up

# API + Anthropic only (cloud)
/opt/mathocr docker compose --profile backend up

# With Ollama
/opt/mathocr docker compose --profile ollama --profile frontend up
```

---

## Tasks

### Phase 1 — Backend Core
- [ ] Task 1: Create `backend/main.py` FastAPI skeleton with CORS
- [ ] Task 2: Create `backend/config.py` env-driven settings
- [ ] Task 3: Create `backend/db/models.py` Job + Settings SQLAlchemy models
- [ ] Task 4: Create `backend/db/database.py` session management
- [ ] Task 5: Create `backend/routers/ocr.py` upload + job creation endpoint
- [ ] Task 6: Create `backend/routers/history.py` CRUD for past jobs
- [ ] Task 7: Create `backend/routers/settings.py` provider config CRUD

### Phase 2 — LLM Provider Abstraction
- [ ] Task 8: Create `backend/llm/base.py` abstract LLMProvider class
- [ ] Task 9: Create `backend/llm/registry.py` provider registry
- [ ] Task 10: Create `backend/llm/fastflowlm.py` FastFlowLM adapter
- [ ] Task 11: Create `backend/llm/ollama.py` Ollama adapter
- [ ] Task 12: Create `backend/llm/vllm.py` vLLM adapter
- [ ] Task 13: Create `backend/llm/openai.py` OpenAI-compatible adapter
- [ ] Task 14: Create `backend/llm/anthropic.py` Anthropic adapter
- [ ] Task 15: Create `backend/llm/lmstudio.py`, `jan.py`, `localai.py`
- [ ] Task 16: Create `backend/llm/factory.py` factory from config

### Phase 3 — OCR Engine
- [ ] Task 17: Create `backend/services/pdf_utils.py` pdftoppm wrapper
- [ ] Task 18: Create `backend/services/latex_cleaner.py` normalization
- [ ] Task 19: Create `backend/services/ocr_engine.py` job processor with WebSocket

### Phase 4 — Frontend
- [ ] Task 20: Create `frontend/index.html` shell + KaTeX CDN
- [ ] Task 21: Create `frontend/style.css` layout (sidebar + main + dropzone)
- [ ] Task 22: Create `frontend/components/DropZone.js` drag-and-drop upload
- [ ] Task 23: Create `frontend/components/ResultPanel.js` KaTeX render + copy
- [ ] Task 24: Create `frontend/components/HistoryPanel.js` past jobs list
- [ ] Task 25: Create `frontend/components/ProviderSelector.js` provider switcher
- [ ] Task 26: Create `frontend/main.js` app wiring + WebSocket client

### Phase 5 — Docker
- [ ] Task 27: Create `Dockerfile.backend` (Python 3.11 slim)
- [ ] Task 28: Create `Dockerfile.frontend` (Nginx Alpine)
- [ ] Task 29: Create `Dockerfile.allinone` (multistage, everything)
- [ ] Task 30: Create `docker-compose.yml` with all profiles
- [ ] Task 31: Create `.env.example` with all provider vars documented
- [ ] Task 32: Create `README.md` with quickstart for each profile

---

## Verification

- Backend: `curl http://localhost:8000/api/providers` → lists all providers
- OCR: `curl -X POST -F "file=@test.png" http://localhost:8000/api/ocr/upload` → job_id
- History: `curl http://localhost:8000/api/history` → paginated list
- Frontend: open `http://localhost:3000`, drop an image, see LaTeX rendered in <5s (local NPU)
