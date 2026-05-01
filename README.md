# MathOCR

Extract LaTeX from images and PDFs of math content using a local LLM.

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/phantomic12/hermes-webui.git mathocr
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

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ocr/upload` | Upload image/PDF, returns `{job_id}` |
| `GET` | `/api/ocr/status/{job_id}` | Job status + progress |
| `GET` | `/api/ocr/result/{job_id}` | LaTeX result |
| `WS` | `/api/ocr/ws/{job_id}` | Stream progress |
| `GET` | `/api/history` | Paginated job history |
| `DELETE` | `/api/history/{job_id}` | Delete job |
| `GET` | `/api/settings` | Active provider |
| `PUT` | `/api/settings` | Switch provider |
| `GET` | `/health` | Health check |

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
