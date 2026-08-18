"""
PHASE 3 - Retriever.

The single entry point the rest of the application uses to search knowledge.
Loads the index once, embeds a query, searches, filters weak matches, and
returns results with full metadata.

WHY A MINIMUM SCORE:
Vector search always returns its top_k, even for a question the corpus cannot
answer - the nearest neighbours are simply the least-bad ones. Filtering on a
similarity floor is what lets the pipeline say "I don't have knowledge on this"
instead of confidently answering from irrelevant chunks. That behaviour is the
main defence against fabricated answers in Phase 4.

WHY DEDUPLICATION BY DOCUMENT:
Adjacent chunks from one document are often all similar to the query, which
would fill the context window with near-duplicates from a single source.
Capping chunks per document keeps retrieved context diverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import (
    RETRIEVAL_MAX_PER_DOC,
    RETRIEVAL_MIN_SCORE,
    RETRIEVAL_TOP_K,
)
from backend.rag.embeddings import embed_query
from backend.rag.hybrid_search import BM25Index, reciprocal_rank_fusion
from backend.rag.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    """One search result: the knowledge text plus where it came from."""

    chunk_id: str
    text: str
    doc_id: str
    title: str
    category: str
    section: str
    source: str
    score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
    retriever: str = "hybrid"

    def as_source(self) -> dict[str, Any]:
        """Compact form for the API 'sources' field shown to the investigator."""
        return {
            "chunk_id": self.chunk_id,
            "document": self.doc_id,
            "title": self.title,
            "section": self.section,
            "category": self.category,
            "source": self.source,
            "similarity_score": round(self.score, 4),
            "matched_by": self.retriever,
        }


class KnowledgeRetriever:
    """Semantic search over the curated knowledge base."""

    def __init__(self, store: VectorStore | None = None,
                 use_hybrid: bool = True):
        self._store = store
        self._bm25: BM25Index | None = None
        self.use_hybrid = use_hybrid

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            self._store = VectorStore.load()
        return self._store

    @property
    def bm25(self) -> BM25Index:
        """Built lazily from the same metadata the dense index holds, so the
        two retrievers are always over an identical chunk set."""
        if self._bm25 is None:
            self._bm25 = BM25Index()
            self._bm25.build(self.store.metadata)
        return self._bm25

    def retrieve(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
        min_score: float = RETRIEVAL_MIN_SCORE,
        max_per_document: int = RETRIEVAL_MAX_PER_DOC,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        """
        Search the knowledge base.

        Returns [] when nothing clears min_score - the caller must treat that
        as "no knowledge available", never as a reason to answer from memory.
        """
        if not query or not query.strip():
            return []

        # Over-fetch, because filtering by score, category and per-document cap
        # will discard some of what comes back.
        fetch_k = max(top_k * 4, 20)

        query_vector = embed_query(query)
        dense = self.store.search(query_vector, top_k=fetch_k)

        if not self.use_hybrid:
            return self._assemble(
                [(m, s, i + 1, None) for i, (m, s) in enumerate(dense)],
                top_k, min_score, max_per_document, category, "dense",
            )

        sparse = self.bm25.search(query, top_k=fetch_k)
        fused = reciprocal_rank_fusion(dense, sparse)

        # A hit found ONLY by keyword search has no cosine similarity, so the
        # similarity floor cannot apply to it. That is intended: an exact code
        # match is strong evidence of relevance in its own right.
        candidates = []
        for h in fused:
            score = h.dense_score if h.dense_score is not None else 0.0
            if h.dense_rank is not None and score < min_score:
                continue
            candidates.append((h.metadata, score, h.dense_rank, h.sparse_rank))

        return self._assemble(candidates, top_k, min_score, max_per_document,
                              category, "hybrid")

    @staticmethod
    def _assemble(candidates, top_k, min_score, max_per_document,
                  category, mode) -> list[RetrievedChunk]:
        results: list[RetrievedChunk] = []
        per_doc: dict[str, int] = {}

        for meta, score, drank, srank in candidates:
            if mode == "dense" and score < min_score:
                continue
            if category and meta.get("category") != category:
                continue

            doc_id = meta.get("doc_id", "")
            if per_doc.get(doc_id, 0) >= max_per_document:
                continue
            per_doc[doc_id] = per_doc.get(doc_id, 0) + 1

            if mode == "dense":
                matched = "dense"
            elif drank is not None and srank is not None:
                matched = "both"
            elif srank is not None:
                matched = "keyword"
            else:
                matched = "dense"

            results.append(
                RetrievedChunk(
                    chunk_id=meta.get("chunk_id", ""),
                    text=meta.get("text", ""),
                    doc_id=doc_id,
                    title=meta.get("title", ""),
                    category=meta.get("category", ""),
                    section=meta.get("section", ""),
                    source=meta.get("source", ""),
                    score=score,
                    dense_rank=drank,
                    sparse_rank=srank,
                    retriever=matched,
                )
            )
            if len(results) >= top_k:
                break

        return results


# Shared instance so the index is loaded once per process.
_retriever: KnowledgeRetriever | None = None


def get_retriever() -> KnowledgeRetriever:
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever
