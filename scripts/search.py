"""
Test knowledge retrieval from the terminal.

    python scripts/search.py "what is upcoding"
    python scripts/search.py                      # interactive mode

Shows what the LLM would receive as grounding in Phase 4, so retrieval quality
can be judged before any model is involved.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.retriever import get_retriever    # noqa: E402


def show(query: str, top_k: int = 5) -> None:
    results = get_retriever().retrieve(query, top_k=top_k)

    print("\n" + "=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    if not results:
        print("\nNo knowledge above the similarity threshold.")
        print("The bot would say it has no knowledge on this, rather than guess.")
        return

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] score {r.score:.4f}   {r.category}/{r.doc_id}")
        print(f"    section: {r.section}")
        print(f"    chunk:   {r.chunk_id}")
        text = r.text if len(r.text) <= 400 else r.text[:400] + "..."
        for line in text.splitlines():
            print(f"    | {line}")


def main() -> int:
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
        return 0

    print("Knowledge search. Blank line or Ctrl-C to quit.")
    while True:
        try:
            q = input("\nquery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            return 0
        show(q)


if __name__ == "__main__":
    raise SystemExit(main())
