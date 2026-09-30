"""
Stage: TEXT -> PARENT CHUNKS -> CHILD CHUNKS

Implements the "search small, retrieve big" strategy:
- Parent chunks are larger and are what gets sent to the LLM as context.
- Child chunks are smaller and are what gets embedded and searched against.

Every child records its parent_id so the retrieval stage can later map
"the precise thing we found" back to "the context worth showing the LLM".
"""
import uuid
from dataclasses import dataclass, field
from typing import List

from app.ingestion.extractor import PageText
from app import config


@dataclass
class ParentChunk:
    id: str
    document_id: str
    text: str
    page_number: int
    order: int  # position within the document, for stable ordering


@dataclass
class ChildChunk:
    id: str
    parent_id: str
    document_id: str
    text: str
    page_number: int
    order: int  # position within the parent


def _split_with_overlap(text: str, size: int, overlap: int) -> List[str]:
    """Simple character-based sliding window split. Tries to break on a
    whitespace boundary near the target size to avoid mid-word cuts,
    but falls back to a hard cut if none is found."""
    if len(text) <= size:
        return [text] if text.strip() else []

    if overlap >= size:
        raise ValueError("overlap must be smaller than chunk size")

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # try to break on the last whitespace within the window
            break_point = text.rfind(" ", start, end)
            if break_point != -1 and break_point > start:
                end = break_point
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


def chunk_document(document_id: str, pages: List[PageText]) -> tuple[List[ParentChunk], List[ChildChunk]]:
    """
    Builds parent chunks per page (concatenated across the page's text,
    split at PARENT_CHUNK_SIZE), then splits each parent into child
    chunks at CHILD_CHUNK_SIZE.
    """
    parents: List[ParentChunk] = []
    children: List[ChildChunk] = []

    parent_order = 0
    child_order_global = 0

    for page in pages:
        if not page.text.strip():
            continue

        parent_texts = _split_with_overlap(
            page.text, config.PARENT_CHUNK_SIZE, config.PARENT_CHUNK_OVERLAP
        )

        for p_text in parent_texts:
            parent_id = str(uuid.uuid4())
            parent = ParentChunk(
                id=parent_id,
                document_id=document_id,
                text=p_text,
                page_number=page.page_number,
                order=parent_order,
            )
            parents.append(parent)
            parent_order += 1

            child_texts = _split_with_overlap(
                p_text, config.CHILD_CHUNK_SIZE, config.CHILD_CHUNK_OVERLAP
            )
            for c_order, c_text in enumerate(child_texts):
                children.append(
                    ChildChunk(
                        id=str(uuid.uuid4()),
                        parent_id=parent_id,
                        document_id=document_id,
                        text=c_text,
                        page_number=page.page_number,
                        order=c_order,
                    )
                )
                child_order_global += 1

    if not parents:
        raise ValueError("No parent chunks were produced from this document.")
    if not children:
        raise ValueError("No child chunks were produced from this document.")

    return parents, children
