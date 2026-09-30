"""
Stage: TEXT -> EMBEDDINGS (both child-chunk embedding at ingestion time
and query embedding at retrieval time)

Uses Ollama's embedding endpoint rather than a local torch/sentence-
transformers embedding model, to reuse the runtime you already have
installed and avoid pulling in a second heavy ML dependency stack.
"""
from typing import List

import requests

from app import config


class EmbeddingError(Exception):
    """Raised when Ollama cannot be reached or the model isn't available.
    Kept distinct from generic exceptions so the pipeline can report
    'embedding stage failed' rather than a vague 500."""
    pass


def _post_embed(text: str) -> List[float]:
    url = f"{config.OLLAMA_BASE_URL}/api/embed"
    try:
        resp = requests.post(
            url,
            json={"model": config.EMBEDDING_MODEL, "input": text},
            timeout=60,
        )
    except requests.exceptions.ConnectionError as e:
        raise EmbeddingError(
            f"Could not connect to Ollama at {config.OLLAMA_BASE_URL}. "
            f"Is 'ollama serve' running?"
        ) from e
    except requests.exceptions.Timeout as e:
        raise EmbeddingError("Ollama embedding request timed out.") from e

    if resp.status_code == 404:
        # Older Ollama versions only expose /api/embeddings (singular, one input at a time)
        return _post_embed_legacy(text)

    if resp.status_code != 200:
        raise EmbeddingError(
            f"Ollama embedding request failed ({resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    # /api/embed returns {"embeddings": [[...]]} for one or more inputs
    embeddings = data.get("embeddings")
    if not embeddings:
        raise EmbeddingError(f"Ollama returned no embeddings: {data}")
    return embeddings[0]


def _post_embed_legacy(text: str) -> List[float]:
    url = f"{config.OLLAMA_BASE_URL}/api/embeddings"
    try:
        resp = requests.post(
            url, json={"model": config.EMBEDDING_MODEL, "prompt": text}, timeout=60
        )
    except requests.exceptions.ConnectionError as e:
        raise EmbeddingError(
            f"Could not connect to Ollama at {config.OLLAMA_BASE_URL}."
        ) from e

    if resp.status_code != 200:
        raise EmbeddingError(
            f"Ollama embedding request failed ({resp.status_code}): {resp.text[:300]}\n"
            f"Is model '{config.EMBEDDING_MODEL}' pulled? Run: ollama pull {config.EMBEDDING_MODEL}"
        )

    data = resp.json()
    embedding = data.get("embedding")
    if not embedding:
        raise EmbeddingError(f"Ollama returned no embedding: {data}")
    return embedding


def embed_text(text: str) -> List[float]:
    """Embed a single string (used for the query at retrieval time)."""
    return _post_embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed multiple strings (used for child chunks at ingestion time).
    Ollama's /api/embed supports batched input directly; we still fall
    back to one-by-one if that fails, so a single bad chunk doesn't
    silently corrupt the whole batch's alignment."""
    url = f"{config.OLLAMA_BASE_URL}/api/embed"
    try:
        resp = requests.post(
            url, json={"model": config.EMBEDDING_MODEL, "input": texts}, timeout=180
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
    except requests.exceptions.RequestException:
        pass

    # Fallback: one request per chunk. Slower but robust.
    return [embed_text(t) for t in texts]
