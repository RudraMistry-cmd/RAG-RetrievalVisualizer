"""
Stage: SELECTED CHILDREN -> PARENT LOOKUP -> DEDUPLICATION -> CONTEXT ASSEMBLY

Takes the reranked, top-N child chunks and resolves them to their parent
chunks (the larger context actually sent to the LLM), collapsing
duplicates when multiple selected children share a parent.
"""
from typing import List

from app.store import sqlite_store as store


def build_context(selected_children: List[dict], session_id: str = None) -> dict:
    """
    selected_children: the post-rerank, top-N list (each dict has at
    least 'parent_id', 'child_id').

    Resolves each child to its parent chunk and labels every block with
    the document it came from, so the SAME function works for a single
    document or for a query searched across many documents. Returns the
    parent texts (deduplicated, order preserved) plus a single assembled
    context string ready to hand to the LLM.
    """
    parent_ids_in_order = [c["parent_id"] for c in selected_children]
    parents = store.get_parents_by_ids(parent_ids_in_order, session_id=session_id)

    # Multiple parents may come from different documents; resolve each
    # document id to its filename for the "Source:" header.
    source_filenames = {
        d["id"]: d["filename"]
        for d in store.get_documents_by_ids([p["document_id"] for p in parents], session_id=session_id)
    }

    blocks = []
    for p in parents:
        header = f"Source: {source_filenames.get(p['document_id'], 'unknown')}"
        if p["page_number"]:
            header += f", Page: {p['page_number']}"
        blocks.append(f"{header}\n\n{p['text']}")

    separator = "\n\n" + ("-" * 40) + "\n\n"
    assembled = separator.join(blocks)

    return {
        "parents_used": [
            {
                "parent_id": p["id"],
                "document_id": p["document_id"],
                "source": source_filenames.get(p["document_id"], "unknown"),
                "page_number": p["page_number"],
                "text": p["text"],
            }
            for p in parents
        ],
        "deduplicated_from": len(parent_ids_in_order),
        "unique_parents": len(parents),
        "assembled_context": assembled,
    }
