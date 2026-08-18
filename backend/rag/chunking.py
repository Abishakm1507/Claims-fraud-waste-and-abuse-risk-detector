"""
PHASE 2 - Chunking.

Splits documents into retrievable pieces.

WHY HEADING-AWARE RATHER THAN FIXED-SIZE:
The knowledge base is deliberately heading-structured. Each "## " section is a
self-contained concept, and inside it sit the five parts (what it means / why
suspicious / how it appears / legitimate explanations / what to examine).

A blind fixed-size split would routinely cut a concept away from its
"Possible legitimate explanations" - exactly the content the bot needs to
avoid presenting only the incriminating reading of a pattern.

So: split on "## " boundaries first, and only sub-split a section that exceeds
the size budget. Sub-splits break on paragraph boundaries, never mid-sentence.

Every chunk is prefixed with "Document title > Section" so the embedding
carries topical context even when the section text alone is ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.config import CHUNK_OVERLAP, CHUNK_SIZE
from backend.rag.ingestion import KnowledgeDocument, load_knowledge_base

H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
H2_SPLIT_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# A section shorter than this is dropped rather than kept as its own chunk.
# Prevents one-line separators becoming standalone "results".
MIN_SECTION_CHARS = 120

# "Related" sections are cross-reference lists of other document names. They are
# navigation aids for a human reader, not knowledge. Indexing them lets a query
# match a list of doc_ids and return it as if it were an answer, so they are
# excluded from the retrievable corpus.
SKIP_SECTIONS = {"related", "see also"}


@dataclass
class Chunk:
    """One retrievable unit of knowledge."""

    chunk_id: str
    text: str          # what gets embedded (includes the context prefix)
    raw_text: str      # the section content alone, for display
    doc_id: str
    title: str
    category: str
    section: str
    source: str
    tags: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        """Stored alongside the vector; returned with every search result."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "section": self.section,
            "source": self.source,
            "tags": self.tags,
            "text": self.raw_text,
        }


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:45] or "section"


def _split_into_sections(body: str) -> list[tuple[str, str]]:
    """
    Split a document body into (section_name, section_text) pairs on "## ".

    Content before the first "## " becomes the "Overview" section, so a
    document's opening definition is never dropped.
    """
    body = H1_RE.sub("", body, count=1).strip()

    matches = list(H2_SPLIT_RE.finditer(body))
    if not matches:
        return [("Overview", body)] if body.strip() else []

    sections: list[tuple[str, str]] = []

    preamble = body[: matches[0].start()].strip()
    # Strip "---" rules used purely as visual separators.
    preamble = re.sub(r"^-{3,}$", "", preamble, flags=re.MULTILINE).strip()
    if len(preamble) >= MIN_SECTION_CHARS:
        sections.append(("Overview", preamble))

    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end]
        text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE).strip()
        if text:
            sections.append((name, text))

    return sections


def _split_long_text(text: str, size: int, overlap: int) -> list[str]:
    """
    Break an oversized section on paragraph boundaries.

    Paragraphs are kept whole where possible. A single paragraph longer than
    the budget is split on sentence boundaries as a last resort. The tail of
    the previous chunk is repeated as overlap so a concept spanning the seam
    is still retrievable from either side.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    units: list[str] = []
    for para in paragraphs:
        if len(para) <= size:
            units.append(para)
            continue
        # Oversized single paragraph - split on sentence ends.
        sentences = re.split(r"(?<=[.:;])\s+", para)
        buf = ""
        for sent in sentences:
            if buf and len(buf) + len(sent) + 1 > size:
                units.append(buf.strip())
                buf = sent
            else:
                buf = f"{buf} {sent}".strip()
        if buf.strip():
            units.append(buf.strip())

    chunks: list[str] = []
    buf = ""
    for unit in units:
        if buf and len(buf) + len(unit) + 2 > size:
            chunks.append(buf.strip())
            tail = buf[-overlap:] if overlap > 0 else ""
            # Start the overlap at a clean boundary rather than mid-word.
            if tail:
                cut = tail.find(" ")
                tail = tail[cut + 1:] if cut != -1 else ""
            buf = f"{tail}\n\n{unit}".strip() if tail else unit
        else:
            buf = f"{buf}\n\n{unit}".strip() if buf else unit
    if buf.strip():
        chunks.append(buf.strip())

    return chunks


def chunk_document(
    doc: KnowledgeDocument,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Turn one document into a list of Chunks."""
    sections = _split_into_sections(doc.body)
    chunks: list[Chunk] = []

    for section_name, section_text in sections:
        if section_name.strip().lower() in SKIP_SECTIONS:
            continue

        parts = (
            [section_text]
            if len(section_text) <= chunk_size
            else _split_long_text(section_text, chunk_size, chunk_overlap)
        )

        for idx, part in enumerate(parts):
            if len(part.strip()) < 40:      # drop stray fragments
                continue

            chunk_id = f"{doc.doc_id}::{_slug(section_name)}::{idx}"

            # Context prefix: gives the embedding the document and section
            # topic, so a chunk like "- Data entry errors..." is not adrift.
            prefix = f"{doc.title} > {section_name}"
            embed_text = f"{prefix}\n\n{part.strip()}"

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=embed_text,
                    raw_text=part.strip(),
                    doc_id=doc.doc_id,
                    title=doc.title,
                    category=doc.category,
                    section=section_name,
                    source=doc.source_path,
                    tags=doc.tags,
                )
            )

    return chunks


def chunk_documents(documents: list[KnowledgeDocument]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in documents:
        chunks.extend(chunk_document(doc))
    return chunks


if __name__ == "__main__":
    docs = load_knowledge_base()
    chunks = chunk_documents(docs)

    sizes = [len(c.raw_text) for c in chunks]
    print(f"\n{len(docs)} documents -> {len(chunks)} chunks")
    print(f"  chunk size: min {min(sizes)}  max {max(sizes)}  "
          f"avg {sum(sizes) // len(sizes)} chars")

    over = [c for c in chunks if len(c.text) > CHUNK_SIZE + 200]
    print(f"  chunks over budget: {len(over)}")

    print("\n  chunks per document:")
    per_doc: dict[str, int] = {}
    for c in chunks:
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
    for doc_id in sorted(per_doc):
        print(f"    {doc_id:<55} {per_doc[doc_id]:>3}")

    print("\n  sample chunk:")
    sample = chunks[len(chunks) // 2]
    print(f"    id:      {sample.chunk_id}")
    print(f"    section: {sample.section}")
    print(f"    text:    {sample.raw_text[:180]}...")
