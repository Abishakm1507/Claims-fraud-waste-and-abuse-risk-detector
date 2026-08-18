"""
Build the FAISS knowledge index.

    python scripts/build_index.py

Runs the full Phase 2 + 3 pipeline:
    knowledge/*.md -> parse -> chunk -> embed -> FAISS -> vector_store/

Re-run this whenever knowledge documents are added or edited.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import (                                     # noqa: E402
    CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL_NAME,
    FAISS_INDEX_PATH, FAISS_METADATA_PATH, KNOWLEDGE_BASE_DIR,
)
from backend.rag.chunking import chunk_documents                 # noqa: E402
from backend.rag.embeddings import embed_texts                   # noqa: E402
from backend.rag.ingestion import load_knowledge_base            # noqa: E402
from backend.rag.vector_store import VectorStore                 # noqa: E402


def main() -> int:
    started = time.time()

    print("=" * 62)
    print("BUILDING KNOWLEDGE INDEX")
    print("=" * 62)
    print(f"knowledge:  {KNOWLEDGE_BASE_DIR}")
    print(f"model:      {EMBEDDING_MODEL_NAME}")
    print(f"chunking:   size={CHUNK_SIZE} overlap={CHUNK_OVERLAP} (chars)")

    print("\n[1/4] Loading documents...")
    documents = load_knowledge_base()
    if not documents:
        print("  ERROR: no documents found. Nothing to index.")
        return 1
    print(f"      {len(documents)} documents")

    print("\n[2/4] Chunking...")
    chunks = chunk_documents(documents)
    if not chunks:
        print("  ERROR: chunking produced no chunks.")
        return 1
    sizes = [len(c.raw_text) for c in chunks]
    print(f"      {len(chunks)} chunks "
          f"(avg {sum(sizes) // len(sizes)} chars, max {max(sizes)})")

    print("\n[3/4] Embedding...")
    vectors = embed_texts([c.text for c in chunks])
    print(f"      vectors: {vectors.shape}")

    print("\n[4/4] Building and saving FAISS index...")
    store = VectorStore()
    store.build(vectors, [c.metadata() for c in chunks])
    store.save()
    print(f"      {FAISS_INDEX_PATH}")
    print(f"      {FAISS_METADATA_PATH}")

    print("\n" + "=" * 62)
    print(f"DONE - {len(chunks)} chunks indexed in {time.time() - started:.1f}s")
    print("Test it with:  python scripts/search.py \"what is upcoding\"")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
