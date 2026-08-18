"""
Central configuration. Values come from environment variables (.env),
with sensible defaults so the project runs out of the box.

Loaded by every module rather than hard-coding paths or model names.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder containing backend/, frontend/, vector_store/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


def _path(env_key: str, default: str) -> Path:
    raw = os.getenv(env_key) or default
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def _int(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, default))
    except (TypeError, ValueError):
        return default


def _float(env_key: str, default: float) -> float:
    try:
        return float(os.getenv(env_key, default))
    except (TypeError, ValueError):
        return default


# ---------- Paths ----------
KNOWLEDGE_BASE_DIR = _path("KNOWLEDGE_BASE_DIR", "backend/knowledge")
VECTOR_STORE_DIR = _path("VECTOR_STORE_DIR", "vector_store")

# ---------- Embeddings ----------
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)
EMBEDDING_DIMENSION = _int("EMBEDDING_DIMENSION", 384)

# ---------- Chunking ----------
# Measured in characters. MiniLM truncates at ~256 word-pieces (~1000 chars),
# so 800 keeps whole chunks inside the model's window.
CHUNK_SIZE = _int("CHUNK_SIZE", 800)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 120)

# ---------- Vector store ----------
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "knowledge_index")
FAISS_INDEX_PATH = VECTOR_STORE_DIR / f"{FAISS_INDEX_NAME}.faiss"
FAISS_METADATA_PATH = VECTOR_STORE_DIR / f"{FAISS_INDEX_NAME}_metadata.json"

# ---------- Retrieval ----------
RETRIEVAL_TOP_K = _int("RETRIEVAL_TOP_K", 8)
RETRIEVAL_MIN_SCORE = _float("RETRIEVAL_MIN_SCORE", 0.22)
# Sections of one concept (definition / why suspicious / how it appears /
# legitimate explanations / what to examine) live in separate chunks of the
# same document, so the per-document cap must allow several through.
RETRIEVAL_MAX_PER_DOC = _int("RETRIEVAL_MAX_PER_DOC", 4)


# ---------- API ----------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = _int("API_PORT", 8000)
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]


# ---------- Phase 8: structured data ----------
DATA_RAW_DIR = _path("DATA_RAW_DIR", "data_raw")
DATA_STORE_DIR = _path("DATA_STORE_DIR", "data_store")
WAREHOUSE_PATH = DATA_STORE_DIR / "warehouse.duckdb"
# Peer cohorts smaller than this fall back to a national cohort, because a
# handful of providers cannot define a meaningful distribution.
MIN_PEER_COHORT = _int("MIN_PEER_COHORT", 20)
