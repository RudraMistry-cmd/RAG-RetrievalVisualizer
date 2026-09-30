"""
Centralized configuration for the RAG Visualizer backend.

Keep every tunable pipeline parameter here so behavior can be changed
without hunting through modules. Defaults are chosen for a small
educational prototype, not production scale.
"""
import os

# --- Ollama (local LLM runtime) ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.environ.get("LLM_MODEL", "hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M")

# --- Reranker (local cross-encoder via sentence-transformers) ---
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# --- OCR (scanned / image-only PDF pages) ---
# Path to tesseract.exe. If empty, the extractor checks common Windows
# install locations, then falls back to the system PATH.
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "D:/Apps/Tesseract/tesseract.exe")
OCR_DPI = int(os.environ.get("OCR_DPI", "200"))

# --- Chunking ---
# Parent chunks: larger, provide context to the LLM.
# Child chunks: smaller, used for precise vector search ("search small, retrieve big").
PARENT_CHUNK_SIZE = 1200      # characters
PARENT_CHUNK_OVERLAP = 100
CHILD_CHUNK_SIZE = 300        # characters
CHILD_CHUNK_OVERLAP = 50

# --- Retrieval ---
TOP_K = 5          # candidates pulled from vector search
RERANK_TOP_N = 3   # candidates kept after reranking, used to build final context

# --- Storage ---
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
SQLITE_PATH = os.path.join(DATA_DIR, "rag.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

# --- Server ---
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
