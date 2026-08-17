from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multi_agent.data.claim_store import ClaimStore
from multi_agent.orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic multi-agent investigation by claim ID or provider NPI.")
    parser.add_argument("--claim-id", help="Claim ID to investigate", default=None)
    parser.add_argument("--npi", "--provider-id", dest="npi", help="Provider NPI to investigate", default=None)
    args = parser.parse_args()

    orchestrator = Orchestrator()

    if args.npi is not None:
        npi = str(args.npi).strip()
        result = orchestrator.investigate_provider(npi)
        print("Investigation Case")
        print("------------------")
        print(f"Claim ID: {result.claim_id}")
        print(f"Provider NPI: {npi}")
        print(f"Provider ID: {result.provider_id}")
        print(f"Provider ID Type: {result.provider_id_type}")
    else:
        claim_id = args.claim_id
        store = ClaimStore()
        claim = store.get_claim(claim_id) if claim_id else None
        if claim is None:
            sample = store._df.dropna(subset=["CLAIM_ID"]).iloc[0]
            claim_id = str(sample["CLAIM_ID"])
            claim = store.get_claim(claim_id)

        result = orchestrator.investigate_claim(claim_id)
        print("Investigation Case")
        print("------------------")
        print(f"Claim ID: {result.claim_id}")
        print(f"Claim Type: {result.claim_type}")
        print(f"Provider ID: {result.provider_id}")
        print(f"Provider ID Type: {result.provider_id_type}")
    print()
    print("Upstream ML Risk")
    print("----------------")
    print(f"Claim Risk Score: {result.claim_risk_score}")
    print(f"Final Risk Level: {result.final_risk_level}")
    print(f"Final Risk Priority: {result.final_risk_priority}")
    print()
    print("Agents")
    print("------")
    for name in ("billing", "peer", "clinical_rule"):
        route = result.routing.get(name, {})
        status = route.get("status", "NOT_SELECTED")
        selected = route.get("selected", False)
        reason = route.get("reason", "")
        print(f"{name}: {'SUCCESS' if selected and status == 'SUCCESS' else status}")
        if not selected:
            print(f"Reason: {reason}")
    print()
    print("Findings")
    print("--------")
    if not result.findings:
        print("No agent findings produced.")
    else:
        for i, finding in enumerate(result.findings[:5], start=1):
            print(f"{i}. [{finding.agent}] {finding.rule}: {finding.description}")
            if finding.evidence:
                print("   Evidence:")
                for key, value in finding.evidence.items():
                    print(f"   - {key}: {value}")
    print()
    print("Investigation")
    print("-------------")
    print(f"Investigation Risk Score: {result.investigation_risk_score}")
    print(f"Investigation Priority: {result.investigation_priority}")
    print(f"Explanation: {result.explanation}")


if __name__ == "__main__":
    main()
