"""
Stage: QUERY EMBEDDING -> VECTOR RETRIEVAL -> TOP-K CANDIDATES

Thin wrapper around the store's cosine search, returning plain dicts
shaped for direct JSON serialization in the API response — this is the
data structure that gets shown in the Retrieval Inspector view.
"""
from typing import List, Optional

from app.embeddings.ollama_embed import embed_text
from app.store import sqlite_store as store
from app import config


def retrieve(document_id: Optional[str], query: str, top_k: int = None) -> dict:
    """document_id=None searches across all stored documents."""
    top_k = top_k or config.TOP_K

    query_embedding = embed_text(query)

    results = store.vector_search(document_id, query_embedding, top_k)

    return {
        "query": query,
        "document_id": document_id,
        "top_k": top_k,
        "candidates": [
            {
                "rank": i + 1,
                "child_id": r.id,
                "parent_id": r.parent_id,
                "document_id": r.document_id,
                "document_filename": r.document_filename,
                "similarity": round(r.similarity, 4),
                "page_number": r.page_number,
                "text": r.text,
            }
            for i, r in enumerate(results)
        ],
    }
