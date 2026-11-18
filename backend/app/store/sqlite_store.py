"""
Stage: EMBEDDINGS -> VECTOR STORE / VECTOR RETRIEVAL

Deliberately NOT a dedicated vector database (Chroma/Qdrant/FAISS).
At prototype scale (single document, low hundreds of chunks) brute-force
cosine similarity over embeddings held in memory (and persisted to
SQLite as blobs) is fast, has zero moving parts to keep alive during a
live demo, and keeps the whole thing debuggable with a text editor.

Schema mirrors the parent/child relationship described in the design doc:
    documents(id, filename, created_at)
    parents(id, document_id, text, page_number, "order")
    children(id, parent_id, document_id, text, page_number, "order", embedding)
"""
import sqlite3
import struct
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from app import config
from app.ingestion.chunker import ParentChunk, ChildChunk


def _ensure_data_dir():
    import os
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_data_dir()
    conn = sqlite3.connect(config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at REAL NOT NULL,
                session_id TEXT
            );

            CREATE TABLE IF NOT EXISTS parents (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS children (
                id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_order INTEGER NOT NULL,
                embedding BLOB,
                embedding_dim INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_parents_document ON parents(document_id);
            CREATE INDEX IF NOT EXISTS idx_children_parent ON children(parent_id);
            CREATE INDEX IF NOT EXISTS idx_children_document ON children(document_id);

            -- Raw per-page extraction results (text layer and/or OCR), so
            -- the "what exactly was extracted" preview can be rendered.
            CREATE TABLE IF NOT EXISTS extracted_pages (
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                ocr INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (document_id, page_number)
            );
            """
        )
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
        if "session_id" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN session_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id)")
        conn.commit()
    finally:
        conn.close()


def _pack_embedding(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_embedding(blob: bytes, dim: int) -> np.ndarray:
    return np.array(struct.unpack(f"{dim}f", blob), dtype=np.float32)


def create_document(document_id: str, filename: str, session_id: str = None):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO documents (id, filename, created_at, session_id) VALUES (?, ?, ?, ?)",
            (document_id, filename, time.time(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_pages(document_id: str, pages):
    """Persists the raw per-page extraction (text layer or OCR) results."""
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO extracted_pages (document_id, page_number, text, ocr) "
            "VALUES (?, ?, ?, ?)",
            [(document_id, p.page_number, p.text, 1 if p.ocr else 0) for p in pages],
        )
        conn.commit()
    finally:
        conn.close()


def get_document_pages(document_id: str, session_id: str = None) -> List[dict]:
    """Returns every page's extracted text for the extraction preview view."""
    conn = get_connection()
    try:
        doc = conn.execute(
            "SELECT id FROM documents WHERE id = ? AND session_id IS ?",
            (document_id, session_id),
        ).fetchone()
        if not doc:
            raise ValueError(f"No document with id {document_id}")
        rows = conn.execute(
            "SELECT page_number, text, ocr FROM extracted_pages "
            "WHERE document_id = ? ORDER BY page_number",
            (document_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "page_number": r["page_number"],
            "text": r["text"],
            "ocr": bool(r["ocr"]),
            "char_count": len(r["text"]),
        }
        for r in rows
    ]


def insert_parents(parents: List[ParentChunk]):
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT INTO parents (id, document_id, text, page_number, chunk_order) "
            "VALUES (?, ?, ?, ?, ?)",
            [(p.id, p.document_id, p.text, p.page_number, p.order) for p in parents],
        )
        conn.commit()
    finally:
        conn.close()


def insert_children_with_embeddings(children: List[ChildChunk], embeddings: List[List[float]]):
    """embeddings[i] must correspond to children[i]."""
    if len(children) != len(embeddings):
        raise ValueError(
            f"children/embeddings length mismatch: {len(children)} vs {len(embeddings)}"
        )
    conn = get_connection()
    try:
        rows = []
        for c, emb in zip(children, embeddings):
            rows.append((
                c.id, c.parent_id, c.document_id, c.text, c.page_number, c.order,
                _pack_embedding(emb), len(emb),
            ))
        conn.executemany(
            "INSERT INTO children "
            "(id, parent_id, document_id, text, page_number, chunk_order, embedding, embedding_dim) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


@dataclass
class ScoredChild:
    id: str
    parent_id: str
    document_id: str
    document_filename: str
    text: str
    page_number: int
    similarity: float


def vector_search(
    document_id: Optional[str],
    query_embedding: List[float],
    top_k: int,
    session_id: str = None,
) -> List[ScoredChild]:
    """Brute-force cosine similarity over the children of a document.
    Pass document_id=None to search across every stored document in the session.
    Fine at prototype scale; see module docstring for the reasoning."""
    conn = get_connection()
    try:
        if session_id is None:
            rows = conn.execute(
                "SELECT c.id, c.parent_id, c.document_id, c.text, c.page_number, "
                "       c.embedding, c.embedding_dim, d.filename AS document_filename "
                "FROM children c JOIN documents d ON d.id = c.document_id "
                "WHERE (? IS NULL OR c.document_id = ?) AND d.session_id IS NULL",
                (document_id, document_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT c.id, c.parent_id, c.document_id, c.text, c.page_number, "
                "       c.embedding, c.embedding_dim, d.filename AS document_filename "
                "FROM children c JOIN documents d ON d.id = c.document_id "
                "WHERE (? IS NULL OR c.document_id = ?) AND d.session_id = ?",
                (document_id, document_id, session_id),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        raise ValueError("Query embedding is a zero vector; cannot compute similarity.")

    scored = []
    for row in rows:
        vec = _unpack_embedding(row["embedding"], row["embedding_dim"])
        denom = (np.linalg.norm(vec) * q_norm)
        similarity = float(np.dot(vec, q) / denom) if denom != 0 else 0.0
        scored.append(ScoredChild(
            id=row["id"],
            parent_id=row["parent_id"],
            document_id=row["document_id"],
            document_filename=row["document_filename"],
            text=row["text"],
            page_number=row["page_number"],
            similarity=similarity,
        ))

    scored.sort(key=lambda s: s.similarity, reverse=True)
    return scored[:top_k]


def get_parents_by_ids(parent_ids: List[str], session_id: str = None) -> List[dict]:
    """Fetches parents preserving the given id order and de-duplicating
    (a parent may be referenced by multiple selected children)."""
    if not parent_ids:
        return []
    seen = set()
    ordered_unique_ids = []
    for pid in parent_ids:
        if pid not in seen:
            seen.add(pid)
            ordered_unique_ids.append(pid)

    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ordered_unique_ids)
        if session_id is None:
            rows = conn.execute(
                f"SELECT p.id, p.document_id, p.text, p.page_number, p.chunk_order FROM parents p "
                f"JOIN documents d ON d.id = p.document_id "
                f"WHERE p.id IN ({placeholders}) AND d.session_id IS NULL",
                ordered_unique_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT p.id, p.document_id, p.text, p.page_number, p.chunk_order FROM parents p "
                f"JOIN documents d ON d.id = p.document_id "
                f"WHERE p.id IN ({placeholders}) AND d.session_id = ?",
                [*ordered_unique_ids, session_id],
            ).fetchall()
    finally:
        conn.close()

    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[pid] for pid in ordered_unique_ids if pid in by_id]


def get_document(document_id: str, session_id: str = None) -> Optional[dict]:
    conn = get_connection()
    try:
        if session_id is None:
            row = conn.execute(
                "SELECT id, filename, created_at FROM documents WHERE id = ? AND session_id IS NULL",
                (document_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, filename, created_at FROM documents WHERE id = ? AND session_id = ?",
                (document_id, session_id),
            ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_documents_by_ids(document_ids, session_id: str = None) -> List[dict]:
    """Fetches documents (id, filename) for the given ids — used to resolve
    source filenames when context spans multiple documents."""
    document_ids = [d for d in dict.fromkeys(document_ids) if d]
    if not document_ids:
        return []
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in document_ids)
        if session_id is None:
            rows = conn.execute(
                f"SELECT id, filename FROM documents WHERE id IN ({placeholders}) AND session_id IS NULL",
                document_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT id, filename FROM documents WHERE id IN ({placeholders}) AND session_id = ?",
                [*document_ids, session_id],
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_document_structure(document_id: str, session_id: str = None) -> dict:
    """Returns the full parent -> children tree for the structure
    visualization view."""
    conn = get_connection()
    try:
        if session_id is None:
            doc = conn.execute(
                "SELECT id, filename FROM documents WHERE id = ? AND session_id IS NULL",
                (document_id,),
            ).fetchone()
        else:
            doc = conn.execute(
                "SELECT id, filename FROM documents WHERE id = ? AND session_id = ?",
                (document_id, session_id),
            ).fetchone()
        if not doc:
            raise ValueError(f"No document with id {document_id}")

        parents = conn.execute(
            "SELECT id, text, page_number, chunk_order FROM parents "
            "WHERE document_id = ? ORDER BY chunk_order",
            (document_id,),
        ).fetchall()
        children = conn.execute(
            "SELECT id, parent_id, text, page_number, chunk_order FROM children "
            "WHERE document_id = ? ORDER BY chunk_order",
            (document_id,),
        ).fetchall()
    finally:
        conn.close()

    children_by_parent = {}
    for c in children:
        children_by_parent.setdefault(c["parent_id"], []).append({
            "id": c["id"],
            "text": c["text"],
            "page_number": c["page_number"],
            "order": c["chunk_order"],
        })

    return {
        "document_id": doc["id"],
        "filename": doc["filename"],
        "parents": [
            {
                "id": p["id"],
                "text": p["text"],
                "page_number": p["page_number"],
                "order": p["chunk_order"],
                "children": children_by_parent.get(p["id"], []),
            }
            for p in parents
        ],
    }


def list_documents(session_id: str = None) -> List[dict]:
    conn = get_connection()
    try:
        if session_id is None:
            rows = conn.execute(
                "SELECT d.id, d.filename, d.created_at, "
                "(SELECT COUNT(*) FROM parents WHERE document_id = d.id) as parent_count, "
                "(SELECT COUNT(*) FROM children WHERE document_id = d.id) as child_count "
                "FROM documents d WHERE d.session_id IS NULL ORDER BY d.created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.id, d.filename, d.created_at, "
                "(SELECT COUNT(*) FROM parents WHERE document_id = d.id) as parent_count, "
                "(SELECT COUNT(*) FROM children WHERE document_id = d.id) as child_count "
                "FROM documents d WHERE d.session_id = ? ORDER BY d.created_at DESC",
                (session_id,),
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_document(document_id: str, session_id: str = None) -> bool:
    """Removes a document and its chunks (parents/children cascade)."""
    conn = get_connection()
    try:
        if session_id is None:
            cur = conn.execute(
                "DELETE FROM documents WHERE id = ? AND session_id IS NULL",
                (document_id,),
            )
        else:
            cur = conn.execute(
                "DELETE FROM documents WHERE id = ? AND session_id = ?",
                (document_id, session_id),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
