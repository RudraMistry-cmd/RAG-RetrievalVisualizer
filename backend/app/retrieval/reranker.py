"""
Stage: TOP-K CANDIDATES -> RERANKING -> REORDERED RESULTS

Uses a real cross-encoder model (distinct from the embedding model),
which scores each (query, chunk) pair jointly rather than comparing
independently-computed vectors. This is *why* reranking can reorder
results that vector similarity ranked differently: the cross-encoder
sees the query and the chunk together, at the cost of being too slow
to run over an entire corpus (hence it only runs on the Top-K, not
every chunk).

IMPORTANT: cross-encoder scores are NOT cosine similarities and are not
on a 0-1 scale by default here (raw logits from ms-marco-MiniLM). We
deliberately do not rescale them to "look like" the similarity scores,
per the requirement not to imply the two scores are directly comparable.
The frontend should visualize rank movement, not treat the two numbers
as being on the same axis.
"""
from typing import List

from app import config

_model = None


class RerankerError(Exception):
    pass


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise RerankerError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from e
        try:
            _model = CrossEncoder(config.RERANKER_MODEL)
        except Exception as e:
            raise RerankerError(
                f"Failed to load reranker model '{config.RERANKER_MODEL}': {e}"
            ) from e
    return _model


def rerank(query: str, candidates: List[dict], top_n: int = None) -> dict:
    """
    candidates: list of dicts as produced by retriever.retrieve()'s
    "candidates" list (must contain 'text', 'child_id', 'parent_id',
    'similarity', 'page_number').

    Returns both the original order and the reranked order so the
    frontend can render a visual before/after comparison.
    """
    top_n = top_n or config.RERANK_TOP_N
    if not candidates:
        return {"query": query, "before": [], "after": []}

    model = _get_model()

    pairs = [[query, c["text"]] for c in candidates]
    try:
        scores = model.predict(pairs)
    except Exception as e:
        raise RerankerError(f"Reranker inference failed: {e}") from e

    before = [
        {**c, "vector_rank": i + 1}
        for i, c in enumerate(candidates)
    ]

    scored = [
        {**c, "rerank_score": float(score)}
        for c, score in zip(candidates, scores)
    ]
    scored.sort(key=lambda c: c["rerank_score"], reverse=True)

    after = []
    for new_rank, c in enumerate(scored, start=1):
        original_rank = next(
            i + 1 for i, orig in enumerate(candidates) if orig["child_id"] == c["child_id"]
        )
        movement = original_rank - new_rank  # positive = moved up
        after.append({
            **c,
            "rerank_rank": new_rank,
            "vector_rank": original_rank,
            "movement": movement,
        })

    return {
        "query": query,
        "before": before,
        "after": after[:top_n] if top_n else after,
        "after_full": after,  # full reranked list, in case UI wants to show all before truncation
    }
