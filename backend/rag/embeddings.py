"""
PHASE 2 - Embeddings.

Wraps the sentence-transformers model that converts text into vectors.

WHY all-MiniLM-L6-v2:
 - small (~80 MB) and fast on CPU, so no GPU is needed
 - 384 dimensions, which keeps the FAISS index tiny
 - strong quality for short-passage semantic search, which is exactly this task

WHY NORMALISED VECTORS:
Vectors are L2-normalised on output. With normalised vectors, an inner-product
FAISS index computes cosine similarity directly, giving scores in a predictable
0-1 range that a similarity threshold can be set against.

The model is loaded lazily and cached, so importing this module is cheap and the
model is only fetched when something is actually embedded.
"""

from __future__ import annotations

import numpy as np

from backend.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL_NAME

_model = None


def get_model():
    """Load (once) and return the sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed.\n"
                "Install it with:  pip install sentence-transformers"
            ) from exc

        print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        print("(first run downloads ~80 MB, then it is cached locally)")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        actual = _model.get_sentence_embedding_dimension()
        if actual != EMBEDDING_DIMENSION:
            print(
                f"  ! model dimension is {actual} but EMBEDDING_DIMENSION "
                f"is {EMBEDDING_DIMENSION} - using {actual}"
            )
    return _model


def embed_texts(texts: list[str], batch_size: int = 32,
                show_progress: bool = True) -> np.ndarray:
    """Embed a list of texts. Returns float32 array, shape (len(texts), dim)."""
    if not texts:
        return np.zeros((0, EMBEDDING_DIMENSION), dtype="float32")

    model = get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,   # enables cosine similarity via inner product
    )
    return np.asarray(vectors, dtype="float32")


def embed_query(text: str) -> np.ndarray:
    """Embed a single query. Returns shape (1, dim) - ready for FAISS search."""
    return embed_texts([text], show_progress=False)


if __name__ == "__main__":
    samples = [
        "What is upcoding?",
        "Billing a higher level service than was documented.",
        "How many claims did a provider submit?",
    ]
    vecs = embed_texts(samples)
    print(f"\nEmbedded {len(samples)} texts -> shape {vecs.shape}")
    print(f"Norm of first vector: {np.linalg.norm(vecs[0]):.4f} (should be ~1.0)")
    print(f"Similarity, sample 0 vs 1: {float(vecs[0] @ vecs[1]):.4f}")
    print(f"Similarity, sample 0 vs 2: {float(vecs[0] @ vecs[2]):.4f}")
