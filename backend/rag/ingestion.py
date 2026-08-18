"""
PHASE 2 - Document ingestion.

Walks the knowledge base, reads every Markdown document, and separates the
YAML front matter (metadata) from the body (retrievable content).

Nothing here embeds or chunks. This layer only answers:
"what documents exist, and what do we know about each one?"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.config import KNOWLEDGE_BASE_DIR

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# INDEX.md is a human-facing map of the corpus, not domain knowledge.
# Indexing it would let the bot retrieve a table of contents as if it were
# an answer, so it is excluded.
EXCLUDED_FILENAMES = {"INDEX.md"}


@dataclass
class KnowledgeDocument:
    """One Markdown knowledge document, parsed."""

    doc_id: str
    title: str
    category: str
    tags: list[str] = field(default_factory=list)
    source_type: str = "curated_knowledge"
    version: str = ""
    source_path: str = ""
    body: str = ""

    def metadata(self) -> dict[str, Any]:
        """Metadata carried onto every chunk derived from this document."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "tags": self.tags,
            "source_type": self.source_type,
            "version": self.version,
            "source": self.source_path,
        }


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into (front matter dict, body)."""
    match = FRONT_MATTER_RE.match(text.lstrip("\ufeff"))
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    body = text[match.end():]
    return meta, body


def load_document(path: Path, knowledge_root: Path) -> KnowledgeDocument | None:
    """Read and parse a single .md file. Returns None if unusable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  ! could not read {path}: {exc}")
        return None

    meta, body = parse_front_matter(text)

    if not body.strip():
        print(f"  ! empty body, skipping: {path.name}")
        return None

    # Fall back to the file location if front matter is missing a field, so a
    # malformed document degrades rather than breaking the pipeline.
    category = meta.get("category") or path.parent.name
    doc_id = meta.get("doc_id") or f"{category}.{path.stem}"
    title = meta.get("title") or path.stem.replace("_", " ").title()

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    if not meta:
        print(f"  ! no front matter, using defaults: {path.name}")

    return KnowledgeDocument(
        doc_id=str(doc_id),
        title=str(title),
        category=str(category),
        tags=[str(t) for t in tags],
        source_type=str(meta.get("source_type", "curated_knowledge")),
        version=str(meta.get("version", "")),
        source_path=str(path.relative_to(knowledge_root.parent.parent)),
        body=body,
    )


def load_knowledge_base(knowledge_dir: Path | None = None) -> list[KnowledgeDocument]:
    """Load every knowledge document, sorted for reproducible ordering."""
    root = Path(knowledge_dir) if knowledge_dir else KNOWLEDGE_BASE_DIR

    if not root.exists():
        raise FileNotFoundError(
            f"Knowledge directory not found: {root}\n"
            "Run this from the project root, or set KNOWLEDGE_BASE_DIR in .env"
        )

    documents: list[KnowledgeDocument] = []
    seen_ids: dict[str, str] = {}

    for path in sorted(root.rglob("*.md")):
        if path.name in EXCLUDED_FILENAMES:
            continue

        doc = load_document(path, root)
        if doc is None:
            continue

        # Duplicate doc_ids would make sources ambiguous at retrieval time.
        if doc.doc_id in seen_ids:
            print(
                f"  ! duplicate doc_id '{doc.doc_id}' "
                f"({path.name} and {seen_ids[doc.doc_id]}) - keeping first"
            )
            continue
        seen_ids[doc.doc_id] = path.name

        documents.append(doc)

    return documents


if __name__ == "__main__":
    docs = load_knowledge_base()
    print(f"\nLoaded {len(docs)} knowledge documents\n")
    by_category: dict[str, list[KnowledgeDocument]] = {}
    for d in docs:
        by_category.setdefault(d.category, []).append(d)
    for category in sorted(by_category):
        print(f"  {category}/")
        for d in by_category[category]:
            print(f"    {d.doc_id:<55} {len(d.body):>6} chars")
