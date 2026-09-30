"""
RAG Visualizer backend — FastAPI app.

Endpoints are split by pipeline stage so the frontend's Retrieval
Inspector can advance the demo one stage at a time, plus a /query/full
convenience endpoint that runs everything at once.

Errors are caught per-stage and returned with a clear "stage" field
identifying what failed, rather than a generic 500 — important for
live-demo debugging.
"""
import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from app import config, pipeline
from app.store import sqlite_store as store
from app.ingestion.extractor import ExtractionError
from app.embeddings.ollama_embed import EmbeddingError
from app.retrieval.reranker import RerankerError
from app.generation.llm import GenerationError

app = FastAPI(title="RAG Visualizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    store.init_db()


def _stage_error(stage: str, exc: Exception, status: int = 500):
    raise HTTPException(status_code=status, detail={"stage": stage, "message": str(exc)})


# ---------- Ingestion ----------

@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...)):
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    temp_name = f"{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(config.UPLOAD_DIR, temp_name)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        _stage_error("upload", e, status=400)

    try:
        result = pipeline.ingest_document(temp_path, file.filename)
        return result
    except ExtractionError as e:
        _stage_error("extract_text", e, status=422)
    except EmbeddingError as e:
        _stage_error("embed_children", e, status=502)
    except ValueError as e:
        _stage_error("chunk_document", e, status=422)
    except Exception as e:
        _stage_error("ingest", e)


@app.get("/api/documents")
def list_documents():
    return store.list_documents()


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    if not store.delete_document(document_id):
        raise HTTPException(status_code=404, detail=f"No document with id {document_id}")
    return {"deleted": document_id}


@app.get("/api/documents/{document_id}/structure")
def document_structure(document_id: str):
    try:
        return store.get_document_structure(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/documents/{document_id}/extraction")
def document_extraction(document_id: str):
    """Raw per-page extracted text (text layer and/or OCR) — lets the UI
    show exactly what was pulled out of the document, and which pages
    were OCR'd."""
    try:
        return store.get_document_pages(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- Retrieval (stage-by-stage) ----------

class RetrieveRequest(BaseModel):
    document_id: Optional[str] = None  # None = search across all documents
    query: str
    top_k: Optional[int] = None


@app.post("/api/retrieve")
def retrieve(req: RetrieveRequest):
    try:
        return pipeline.stage_retrieve(req.document_id, req.query, req.top_k)
    except ValueError as e:
        _stage_error("retrieve", e, status=404)
    except EmbeddingError as e:
        _stage_error("query_embedding", e, status=502)


class RerankRequest(BaseModel):
    query: str
    candidates: List[dict]
    top_n: Optional[int] = None


@app.post("/api/rerank")
def rerank(req: RerankRequest):
    try:
        return pipeline.stage_rerank(req.query, req.candidates, req.top_n)
    except RerankerError as e:
        _stage_error("rerank", e, status=502)


class BuildContextRequest(BaseModel):
    document_id: Optional[str] = None  # None = context may span documents
    selected_children: List[dict]


@app.post("/api/build-context")
def build_context(req: BuildContextRequest):
    try:
        return pipeline.stage_build_context(req.document_id, req.selected_children)
    except ValueError as e:
        _stage_error("build_context", e, status=404)


class GenerateRequest(BaseModel):
    question: str
    context: str


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        return pipeline.stage_generate(req.question, req.context)
    except GenerationError as e:
        _stage_error("generate", e, status=502)


# ---------- Full pipeline (one-shot) ----------

class FullQueryRequest(BaseModel):
    document_id: Optional[str] = None  # None = search across all documents
    query: str
    top_k: Optional[int] = None
    top_n: Optional[int] = None


@app.post("/api/query/full")
def query_full(req: FullQueryRequest):
    try:
        return pipeline.run_full_query(req.document_id, req.query, req.top_k, req.top_n)
    except ValueError as e:
        _stage_error("retrieve", e, status=404)
    except EmbeddingError as e:
        _stage_error("query_embedding", e, status=502)
    except RerankerError as e:
        _stage_error("rerank", e, status=502)
    except GenerationError as e:
        _stage_error("generate", e, status=502)


@app.get("/api/health")
def health():
    return {"status": "ok"}
