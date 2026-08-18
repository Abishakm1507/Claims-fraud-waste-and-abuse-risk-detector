"""
Phase 1 verification.

Checks that every expected folder exists and reports which of the 20 knowledge
documents are present. Pure structure check - no ingestion, no embeddings.

Run from the project root:  python scripts/verify_structure.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "backend" / "knowledge"

EXPECTED_DIRS = [
    "backend/api",
    "backend/rag",
    "backend/llm",
    "backend/router",
    "backend/data",
    "backend/model",
    "backend/knowledge",
    "frontend",
    "vector_store",
    "scripts",
]

EXPECTED_DOCS = {
    "fraud_concepts": [
        "fwa_fundamentals",
        "coding_misrepresentation",
        "services_not_rendered",
        "unnecessary_and_excessive_services",
        "fraud_actors",
    ],
    "payment_integrity": [
        "payment_integrity_overview",
        "detection_analytics_and_risk_scoring",
    ],
    "fraud_indicators": [
        "volume_and_reimbursement",
        "procedure_and_diagnosis",
        "duplication_and_repetition",
        "peer_deviation_and_outliers",
    ],
    "healthcare_claims": [
        "claims_fundamentals",
        "inpatient_and_outpatient_claims",
        "coding_fundamentals",
    ],
    "investigation": [
        "investigation_workflow",
        "comparison_and_analysis_methods",
        "risk_factor_interpretation",
    ],
    "provider_behavior": [
        "provider_patterns_and_peer_groups",
    ],
    "cms_concepts": [
        "medicare_basics",
        "payment_systems_and_program_integrity",
    ],
}


def check_dirs() -> bool:
    print("Folder structure")
    ok = True
    for rel in EXPECTED_DIRS:
        exists = (ROOT / rel).is_dir()
        ok = ok and exists
        print(f"  [{'x' if exists else ' '}] {rel}")
    return ok


def check_docs() -> tuple[int, int]:
    print("\nKnowledge documents")
    present = 0
    total = 0
    for category, docs in EXPECTED_DOCS.items():
        print(f"\n  {category}/")
        for name in docs:
            total += 1
            path = KNOWLEDGE / category / f"{name}.md"
            if path.exists():
                present += 1
                print(f"    [x] {name}.md")
            else:
                print(f"    [ ] {name}.md   (pending)")
    return present, total


def check_front_matter() -> list[str]:
    """Every knowledge .md must open with a YAML front matter block."""
    problems = []
    for path in KNOWLEDGE.rglob("*.md"):
        text = path.read_text(encoding="utf-8").lstrip()
        if not text.startswith("---"):
            problems.append(str(path.relative_to(ROOT)))
    return problems


if __name__ == "__main__":
    dirs_ok = check_dirs()
    present, total = check_docs()

    problems = check_front_matter()
    print("\nFront matter")
    if problems:
        for p in problems:
            print(f"  [ ] missing front matter: {p}")
    else:
        print("  [x] all knowledge documents have YAML front matter")

    print(f"\nSummary: {present}/{total} knowledge documents present")
    print(f"Folders: {'ok' if dirs_ok else 'INCOMPLETE'}")
    if present < total:
        print("See _PENDING.txt in each category for what remains.")
