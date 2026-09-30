# RAG Retrieval Visualizer

A local, offline RAG pipeline that exposes every intermediate stage
(chunking, embeddings, vector retrieval, reranking, context assembly)
for a live classroom demo.

## Stack
- Backend: Python 3.11 + FastAPI
- Frontend: React + Vite
- Vector store: SQLite (brute-force cosine similarity — fine at this scale)
- Embeddings: Ollama (`nomic-embed-text`)
- Reranker: local cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`, via sentence-transformers)
- LLM: Ollama (`qwen2.5:7b`, already on your machine)

## One-time setup (Windows / PowerShell)

### 1. Pull the embedding model
```powershell
ollama pull nomic-embed-text
```
(`qwen2.5:7b` is already installed, no action needed there.)

### 2. Backend
```powershell
cd backend
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
The first run will also download the cross-encoder reranker (~90MB) from
Hugging Face the first time `/api/rerank` is called — this requires
internet access once, then it's cached locally.

### 3. Frontend
```powershell
cd frontend
npm install
```

## Running it

You need 3 things running simultaneously, each in its own terminal:

```powershell
# Terminal 1 — Ollama (if not already running as a service)
ollama serve

# Terminal 2 — Backend
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm run dev
```

Then open http://localhost:5173

Backend API docs (auto-generated): http://localhost:8000/docs

## Quick health check

```powershell
curl http://localhost:8000/api/health
```
Should return `{"status":"ok"}`.

## Config

All tunable parameters (chunk sizes, Top-K, Top-N, model names) live in
`backend/app/config.py`. No UI exposure needed — edit there and restart
the backend.

## Known first-run gotchas

- If `/api/ingest` fails at the `embed_children` stage: Ollama isn't
  running, or `nomic-embed-text` hasn't been pulled yet.
- If `/api/rerank` fails: check your internet connection for the
  one-time Hugging Face model download, or check disk space (~90MB).
- Only `.pdf`, `.txt`, and `.md` files are supported in this prototype.
- Scanned/image-only PDFs will fail extraction (no OCR in this
  prototype) — this is intentional, not a bug.
