"""
PHASE 10 - Hybrid retrieval.

Combines dense (semantic) and sparse (keyword) search, fusing the two rankings
with Reciprocal Rank Fusion.

WHY HYBRID:
Dense search matches meaning but is weak on exact tokens. This corpus is full of
them - HCPCS codes (Q4205), NPIs, exclusion statutes (1128B4), and scheme names
that must match literally. Embeddings blur those; BM25 nails them.

Conversely BM25 cannot match "billing more than was documented" to a document
about upcoding, because they share no words. Dense handles paraphrase.

So each covers the other's failure mode.

WHY RECIPROCAL RANK FUSION:
Dense returns cosine similarity (0-1); BM25 returns unbounded term-frequency
scores. The two scales are not comparable and normalising them is arbitrary and
corpus-dependent. RRF discards scores and uses only RANK:

    fused(d) = sum over retrievers of  1 / (k + rank(d))

with k=60, the standard damping constant. A document ranked highly by either
retriever scores well; one ranked highly by both scores best. No tuning needed
and no scale mismatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

RRF_K = 60


def tokenize(text: str) -> list[str]:
    """
    Lowercase word tokens, keeping alphanumeric codes intact.

    Codes like Q4205 and 1128B4 must survive as single tokens - splitting them
    would destroy exactly the advantage BM25 provides here.
    """
    return re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.lower())


@dataclass
class FusedHit:
    chunk_id: str
    metadata: dict[str, Any]
    fused_score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None


class BM25Index:
    """Sparse keyword index over the same chunks the dense index holds."""

    def __init__(self) -> None:
        self._bm25 = None
        self._metadata: list[dict[str, Any]] = []

    def build(self, metadata: list[dict[str, Any]]) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise ImportError(
                "rank-bm25 is not installed.\nInstall it with: pip install rank-bm25"
            ) from exc

        self._metadata = metadata
        corpus = [
            tokenize(f"{m.get('title','')} {m.get('section','')} {m.get('text','')}")
            for m in metadata
        ]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 20) -> list[tuple[dict, float]]:
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                break
            out.append((self._metadata[i], float(scores[i])))
        return out

    def __len__(self) -> int:
        return len(self._metadata)


def reciprocal_rank_fusion(
    dense: list[tuple[dict, float]],
    sparse: list[tuple[dict, float]],
    k: int = RRF_K,
) -> list[FusedHit]:
    """Fuse two ranked lists by rank position rather than by score."""
    fused: dict[str, FusedHit] = {}

    for rank, (meta, score) in enumerate(dense, start=1):
        cid = meta.get("chunk_id", "")
        fused[cid] = FusedHit(
            chunk_id=cid, metadata=meta,
            fused_score=1.0 / (k + rank),
            dense_rank=rank, dense_score=score,
        )

    for rank, (meta, _score) in enumerate(sparse, start=1):
        cid = meta.get("chunk_id", "")
        contribution = 1.0 / (k + rank)
        if cid in fused:
            fused[cid].fused_score += contribution
            fused[cid].sparse_rank = rank
        else:
            fused[cid] = FusedHit(
                chunk_id=cid, metadata=meta,
                fused_score=contribution, sparse_rank=rank,
            )

    return sorted(fused.values(), key=lambda h: h.fused_score, reverse=True)
