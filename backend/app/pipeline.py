"""
Orchestrates the full ingestion and retrieval pipelines.

Each stage is a separate, independently callable function so the API
can expose them as distinct steps (letting the presenter advance
'Retrieve -> Rerank -> Build Context -> Generate' one click at a time),
while ingest_document() and run_full_query() provide one-shot versions
for convenience.

Failures are intentionally NOT caught by a blanket try/except here —
each stage raises its own typed exception (ExtractionError,
EmbeddingError, RerankerError, GenerationError) so the API layer can
report exactly which stage failed, per the debuggability requirement.
"""
import uuid
import time

from typing import Optional

from app.ingestion.extractor import extract_text
from app.ingestion.chunker import chunk_document
from app.embeddings.ollama_embed import embed_batch, embed_text
from app.store import sqlite_store as store
from app.retrieval.retriever import retrieve as vector_retrieve
from app.retrieval.reranker import rerank as rerank_candidates
from app.retrieval.context_builder import build_context
from app.generation.llm import generate_answer
from app import config


def ingest_document(file_path: str, filename: str) -> dict:
    """Runs DOCUMENT -> TEXT -> PARENTS -> CHILDREN -> EMBEDDINGS -> STORE."""
    trace = []

    def stamp(stage):
        trace.append({"stage": stage, "at": time.time()})

    # Stage 1 — EXTRACT: pull raw text out of the uploaded file (PDF/TXT/MD),
    # returned as one string per page for downstream chunking.
    stamp("extract_text:start")
    pages = extract_text(file_path, filename)
    stamp("extract_text:done")

    document_id = str(uuid.uuid4())

    # Stage 2 — CHUNK: split the page text into parent chunks (broad context
    # windows) and child chunks (small, precise units that get embedded and
    # searched). Child chunks remember which parent they belong to.
    stamp("chunk_document:start")
    parents, children = chunk_document(document_id, pages)
    stamp("chunk_document:done")

    # Stage 3 — EMBED: turn every child chunk into a vector so it can later
    # be compared against query embeddings for similarity search.
    stamp("embed_children:start")
    child_texts = [c.text for c in children]
    embeddings = embed_batch(child_texts)
    stamp("embed_children:done")

    # Stage 4 — STORE: persist document metadata, parent/child chunks, and
    # their vectors in SQLite so retrieval can query them by document_id.
    stamp("store:start")
    store.create_document(document_id, filename)
    # Stage 4a — persist the raw per-page extraction (text layer and/or OCR)
    # so the UI can preview exactly what was extracted from the document.
    store.insert_pages(document_id, pages)
    store.insert_parents(parents)
    store.insert_children_with_embeddings(children, embeddings)
    stamp("store:done")

    return {
        "document_id": document_id,
        "filename": filename,
        "parent_count": len(parents),
        "child_count": len(children),
        "embedding_count": len(embeddings),
        "embedding_model": config.EMBEDDING_MODEL,
        "pages": len(pages),
        "pages_ocr": sum(1 for p in pages if p.ocr),
        "trace": trace,
    }


def stage_retrieve(document_id: Optional[str], query: str, top_k: int = None) -> dict:
    """Stage: QUERY -> EMBEDDING -> VECTOR SEARCH -> TOP-K

    Embeds the user's query, runs a cosine-similarity search over the
    child-chunk vectors, and returns the top-k closest chunks.
    document_id selects a single document; None searches all documents.
    """
    if document_id:
        doc = store.get_document(document_id)
        if not doc:
            raise ValueError(f"No document with id {document_id}")
    return vector_retrieve(document_id, query, top_k)


def stage_rerank(query: str, candidates: list, top_n: int = None) -> dict:
    """Stage: TOP-K -> RERANK -> REORDERED

    Scores each (query, chunk) pair with a cross-encoder model (which sees
    query and chunk together, unlike vector search) and reorders the list,
    keeping only the best top-n chunks.
    """
    return rerank_candidates(query, candidates, top_n)


def stage_build_context(document_id: Optional[str], selected_children: list) -> dict:
    """Stage: SELECTED CHILDREN -> PARENT LOOKUP -> DEDUP -> CONTEXT

    Maps each selected child back to its parent chunk, collapses duplicate
    parents, and assembles a single context string for the LLM. Parent
    chunks may come from multiple documents (cross-document search); each
    block is labelled with its source filename.
    """
    if document_id:
        doc = store.get_document(document_id)
        if not doc:
            raise ValueError(f"No document with id {document_id}")
    return build_context(selected_children)


def stage_generate(question: str, context: str) -> dict:
    """Stage: CONTEXT -> LLM -> ANSWER

    Sends the question plus the assembled context to the LLM and returns
    the generated answer.
    """
    answer = generate_answer(question, context)
    return {"question": question, "answer": answer, "model": config.LLM_MODEL}


def run_full_query(document_id: Optional[str], query: str, top_k: int = None, top_n: int = None) -> dict:
    """One-shot convenience path running every stage in sequence.
    Returns the full trace so the frontend can render every intermediate
    stage even in 'run all at once' mode."""
    # Stage 1 — embed the query and pull the top-k child chunks from the store.
    retrieval = stage_retrieve(document_id, query, top_k)
    # Stage 2 — rerank those candidates with the cross-encoder for precision.
    reranked = stage_rerank(query, retrieval["candidates"], top_n)
    # Stage 3 — resolve the chosen children to their parent chunks and dedupe.
    context = stage_build_context(document_id, reranked["after"])
    # Stage 4 — hand the assembled context to the LLM and get the answer.
    generation = stage_generate(query, context["assembled_context"])

    return {
        "query": query,
        "retrieval": retrieval,
        "reranking": reranked,
        "context": context,
        "generation": generation,
    }
