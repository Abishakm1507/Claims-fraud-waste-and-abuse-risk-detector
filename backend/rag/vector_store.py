"""
PHASE 3 - FAISS vector store.

Stores chunk vectors and their metadata, and persists both to disk so the index
is built once rather than on every application start.

WHY IndexFlatIP:
"Flat" = exhaustive search, exact results, no approximation. At this corpus size
(a few hundred chunks) it is instant, and it avoids the tuning and accuracy
trade-offs of approximate indexes. "IP" = inner product which, on the normalised
vectors produced by embeddings.py, equals cosine similarity.

If the corpus later grows into the hundreds of thousands of chunks, this is the
one class to revisit - the interface below would not change.

TWO FILES ARE WRITTEN:
  knowledge_index.faiss           - the vectors
  knowledge_index_metadata.json   - chunk metadata, in index order
Position i in the FAISS index corresponds to entry i in the metadata list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from backend.config import (
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    VECTOR_STORE_DIR,
)


class VectorStore:
    """FAISS index plus parallel chunk metadata."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = None
        self.metadata: list[dict[str, Any]] = []

    # ---------- build ----------

    def build(self, vectors: np.ndarray, metadata: list[dict[str, Any]]) -> None:
        """Create a fresh index from vectors and their metadata."""
        import faiss

        if len(vectors) != len(metadata):
            raise ValueError(
                f"vector/metadata length mismatch: "
                f"{len(vectors)} vectors, {len(metadata)} metadata entries"
            )
        if len(vectors) == 0:
            raise ValueError("Cannot build an index from zero vectors")

        self.dimension = int(vectors.shape[1])
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(np.ascontiguousarray(vectors, dtype="float32"))
        self.metadata = metadata

    # ---------- search ----------

    def search(self, query_vector: np.ndarray, top_k: int = 5
               ) -> list[tuple[dict[str, Any], float]]:
        """
        Return up to top_k (metadata, similarity_score) pairs, best first.
        Scores are cosine similarity in roughly 0-1 for normalised vectors.
        """
        if self.index is None:
            raise RuntimeError(
                "No index loaded. Build it first:  python scripts/build_index.py"
            )

        query_vector = np.ascontiguousarray(query_vector, dtype="float32")
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vector, k)

        results: list[tuple[dict[str, Any], float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:                      # FAISS pads with -1
                continue
            results.append((self.metadata[int(idx)], float(score)))
        return results

    # ---------- persistence ----------

    def save(self, index_path: Path = FAISS_INDEX_PATH,
             metadata_path: Path = FAISS_METADATA_PATH) -> None:
        import faiss

        if self.index is None:
            raise RuntimeError("Nothing to save - no index built")

        VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))

        payload = {
            "dimension": self.dimension,
            "count": len(self.metadata),
            "chunks": self.metadata,
        }
        metadata_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, index_path: Path = FAISS_INDEX_PATH,
             metadata_path: Path = FAISS_METADATA_PATH) -> "VectorStore":
        import faiss

        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                f"Vector store not found at {index_path.parent}\n"
                "Build it first:  python scripts/build_index.py"
            )

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        store = cls(dimension=payload.get("dimension", 384))
        store.index = faiss.read_index(str(index_path))
        store.metadata = payload.get("chunks", [])

        if store.index.ntotal != len(store.metadata):
            raise ValueError(
                f"Corrupt vector store: {store.index.ntotal} vectors but "
                f"{len(store.metadata)} metadata entries. Rebuild the index."
            )
        return store

    def __len__(self) -> int:
        return self.index.ntotal if self.index is not None else 0
