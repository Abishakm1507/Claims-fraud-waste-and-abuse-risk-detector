"""
Query the data warehouse directly from the terminal - no LLM involved.

    python scripts/query.py 1003053851           provider lookup
    python scripts/query.py 1003053851 --peers   peer comparison
    python scripts/query.py --top 10             highest paid providers
    python scripts/query.py --status             what is loaded

Useful for confirming a figure the assistant reported.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.data.structured_data_service import get_data_service  # noqa: E402


def render(e) -> None:
    print("\n" + "=" * 72)
    print(e.query_description or "query")
    print("=" * 72)
    if not e.available:
        print(e.message)
        return
    for k, v in e.facts.items():
        print(f"  {k:<34} {v}")
    if e.peer_comparison:
        print("\n  PEER COMPARISON")
        for k, v in e.peer_comparison.items():
            print(f"  {k:<34} {v}")
    if e.records:
        print("\n  RECORDS")
        for r in e.records:
            print("   " + " | ".join(f"{k}={v}" for k, v in r.items() if v is not None))


def main() -> int:
    s = get_data_service()
    args = sys.argv[1:]

    if not args or "--status" in args:
        st = s.status()
        print(f"\nconnected: {st['connected']}")
        print(st["message"])
        for d in st.get("datasets_loaded", []):
            print(f"  {d['table']:<22} {d['rows']:>9,} rows")
        return 0

    if "--top" in args:
        i = args.index("--top")
        n = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() else 10
        render(s.rank_providers(limit=n))
        return 0

    entity = args[0]
    if "--peers" in args:
        render(s.get_peer_comparison(entity))
    elif entity.lstrip("-").isdigit() and entity.startswith("-"):
        render(s.get_claim_facts(entity))
    else:
        render(s.get_provider_facts(entity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
