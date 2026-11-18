"""
Stage: CONTEXT ASSEMBLY -> LLM -> FINAL RESPONSE

Calls the local Ollama model with the assembled context as a system-style
instruction plus the user's question. Kept deliberately simple per the
brief: this project is about retrieval, not LLM orchestration.
"""
import requests

from app import config
from app.inference_queue import inference_queue


class GenerationError(Exception):
    pass


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context below. If the context does not contain enough "
    "information to answer, say so clearly instead of guessing."
)


def _generate_answer_impl(question: str, context: str) -> str:
    url = f"{config.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
    except requests.exceptions.ConnectionError as e:
        raise GenerationError(
            f"Could not connect to Ollama at {config.OLLAMA_BASE_URL}. Is 'ollama serve' running?"
        ) from e
    except requests.exceptions.Timeout as e:
        raise GenerationError("LLM generation timed out.") from e

    if resp.status_code != 200:
        raise GenerationError(
            f"Ollama chat request failed ({resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise GenerationError(f"Ollama returned no content: {data}")
    return content


def generate_answer(question: str, context: str) -> str:
    """Serialized through the inference queue to avoid concurrent VRAM use."""
    return inference_queue.run(_generate_answer_impl, question, context)
