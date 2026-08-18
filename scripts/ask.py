"""
Ask the assistant a question from the terminal - the full pipeline without the
API or the UI.

    python scripts/ask.py "what is upcoding"
    python scripts/ask.py "why was PRV51001 flagged"
    python scripts/ask.py                       # interactive
    python scripts/ask.py "..." --sources       # show retrieved chunks

Shows the routing decision, the answer, the sources, and any warnings about
sources that are not connected.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rag.rag_pipeline import get_pipeline    # noqa: E402


def ask(question: str) -> None:
    result = get_pipeline().ask(question)

    print("\n" + "=" * 72)
    print(f"Q: {question}")
    print(f"   route: {result.question_type}  "
          f"(confidence {result.routing.get('confidence')})")
    ents = result.routing.get("entities") or {}
    if ents:
        print(f"   entities: {ents}")
    print("=" * 72)

    print(f"\n{result.answer}\n")

    if result.risk_score is not None:
        print(f"RISK SCORE: {result.risk_score}")

    # Sources are debug output: shown only with --sources, because when an
    # answer looks wrong the first question is always which chunks fed it.
    if result.sources and "--sources" in sys.argv:
        print("SOURCES")
        for s in result.sources:
            print(f"  [{s['similarity_score']:.3f}] {s['document']} :: {s['section']}")
            print(f"          {s['source']}")

    if result.warnings:
        print("\nNOTES")
        for w in result.warnings:
            print(f"  - {w}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--sources"]
    if args:
        ask(" ".join(args))
        return 0

    print("Ask the investigation assistant. Blank line or Ctrl-C to quit.")
    while True:
        try:
            q = input("\nask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            return 0
        ask(q)


if __name__ == "__main__":
    raise SystemExit(main())
