# MathOCR

Extract LaTeX from images and PDFs of math content using a local LLM.

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/phantomic12/mathocr.git
cd mathocr
cp .env.example .env
# Edit .env — set MATHOCR_PROVIDER and provider-specific vars
```

### 2. Run

**All-in-one (backend + frontend in one container):**
```bash
docker compose --profile allinone up --build
# Frontend: http://localhost:8080
# API:      http://localhost:8000
```

**Separate backend + frontend (for development):**
```bash
docker compose --profile backend up --build   # API on :8000
docker compose --profile frontend up --build  # UI on :8080
```

**With your own LLM (Ollama):**
```bash
# Install Ollama separately, pull a model, then:
docker compose --profile backend --profile ollama up --build
```

### 3. Use

1. Open http://localhost:8080 (or :8000 for allinone)
2. Drag & drop an image or PDF, or click Browse
3. Wait for processing — LaTeX renders inline via KaTeX

---

## Profiles

| Profile | Services | Use case |
|---------|----------|----------|
| `allinone` | backend + nginx | Single container, simplest deploy |
| `backend` | FastAPI API | API only, custom frontend |
| `frontend` | Nginx SPA | Serve built UI, needs backend |
| `ollama` | Ollama LLM | Self-hosted model |
| `vllm` | vLLM server | High-throughput model serving |

---

## Providers

Set `MATHOCR_PROVIDER` in `.env`:

| Provider | ENV prefix | Notes |
|----------|-----------|-------|
| FastFlowLM (NPU) | `FASTFLOWLM_*` | Default, local AMD Ryzen AI |
| Ollama | `OLLAMA_*` | `ollama pull <model>` first |
| vLLM | `VLLM_*` | HuggingFace model name |
| OpenAI-compatible | `OPENAI_*` | Any OpenAI API compatible endpoint |
| Anthropic | `ANTHROPIC_*` | Claude models |
| LM Studio | `LMSTUDIO_*` | Local GGUF models |
| Jan | `JAN_*` | Local endpoint |
| LocalAI | `LOCALAI_*` | Local endpoint |
| Modal | `MODAL_*` | Serverless |

---

## Development

```bash
# Backend
cd backend
pip install -r ../requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (dev with HMR)
cd frontend
npm install
npm run dev   # proxies /api to :8000
```

## Authentication

MathOCR uses email/password authentication with JWT bearer tokens.

**Roles:**
- **User** — can upload files, view history, and export results
- **Admin** — can do everything a user can, plus manage users (promote/demote/delete) and change provider settings

**To create the first admin account**, set the bootstrap variables in `.env` before registering:

```bash
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=yourpassword
```

Then register with those exact credentials — the first registration matching `ADMIN_EMAIL`+`ADMIN_PASSWORD` is automatically promoted to admin.

Admins can promote/demote other users via the sidebar admin panel in the UI, or via the API:

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}'
# Returns: { "access_token": "...", "user": { "id": "...", "is_admin": true, ... } }

# List all users (admin only)
curl http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer <token>"

# Promote a user
curl -X POST http://localhost:8000/api/admin/users/<user_id>/promote \
  -H "Authorization: Bearer <token>"
```

---

## API
|--------|------|-------------|
| `POST` | `/api/ocr/upload` | Upload image/PDF, returns `{job_id}` |
| `GET`  | `/api/ocr/status/{job_id}` | Job status + progress |
| `GET`  | `/api/ocr/result/{job_id}` | LaTeX result |
| `WS`   | `/api/ocr/ws/{job_id}` | Stream progress |
| `GET`  | `/api/history` | Paginated job history |
| `DELETE`| `/api/history/{job_id}` | Delete job |
| `POST` | `/api/ocr/export/docx/{job_id}` | Export as Word (DOCX) |
| `POST` | `/api/ocr/export/pdf/{job_id}` | Export as PDF |
| `POST` | `/api/ocr/export/epub/{job_id}` | Export as EPUB |
| `GET`  | `/api/providers` | List available providers |
| `GET`  | `/api/settings` | Active provider config |
| `PUT`  | `/api/settings` | Update provider config (admin only) |
| `POST` | `/api/auth/register` | Register account |
| `POST` | `/api/auth/login` | Login, returns JWT |
| `GET`  | `/api/admin/users` | List all users (admin only) |
| `POST` | `/api/admin/users/{user_id}/promote` | Make admin (admin only) |
| `POST` | `/api/admin/users/{user_id}/demote` | Revoke admin (admin only) |
| `DELETE`| `/api/admin/users/{user_id}` | Delete user (admin only) |
| `GET`  | `/health` | Health check |

---

## Files

```
mathocr/
├── backend/              # FastAPI app
│   ├── llm/              # Provider adapters
│   ├── routers/          # API routes
│   ├── services/         # PDF utils, LaTeX cleaner, OCR engine
│   └── main.py           # Entry point
├── frontend/             # Static SPA (served by nginx)
│   ├── index.html
│   ├── main.js
│   └── style.css
├── docker-compose.yml
├── Dockerfile.backend    # API-only image
├── Dockerfile.frontend   # Nginx SPA image
├── Dockerfile.allinone   # Combined image
├── requirements.txt
└── .env.example
```
