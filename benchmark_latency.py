#!/usr/bin/env python
"""Benchmark latency of orchestrator investigation with parallelization.

Measures end-to-end latency for a realistic case with and without parallelization.
"""

import time
from multi_agent.orchestrator import Orchestrator
from multi_agent.schemas.claim_context import ClaimContext, EvidenceBundle
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.schemas.investigation_case import InvestigationCase


def create_sample_case():
    """Create a realistic investigation case."""
    claim = ClaimContext(
        claim_id="CLM-12345",
        claim_type="INPATIENT",
        provider_id="PROV-999",
        claim_risk_score=45.0,
        financial_evidence=EvidenceBundle(
            available=True,
            values={
                "high_outlier_charges": ["dialysis session charged at 300% regional avg"],
                "billing_anomalies": ["unbundled procedures not typically separated"],
            }
        ),
        utilization_evidence=EvidenceBundle(
            available=True,
            values={
                "frequency_concern": ["30 inpatient stays in 12 months (avg regional is 5)"],
                "length_of_stay": ["avg 7 days vs 3.2 days regional average"],
            }
        ),
    )

    provider = ProviderContext(
        npi=1003052788,
        provider_type="Individual",
        provider_state="CA",
        provider_risk_score=45.0,
        risk_tier="Medium",
        peer_deviation_score=0.40,
        geo_deviation_score=0.38,
        deviation_ratio=1.22,
        percentile=65.0,
    )

    case = InvestigationCase(
        case_id="CASE-BENCH-001",
        claim_id=claim.claim_id,
        claim=claim,
        provider=provider,
    )
    return case


def benchmark_orchestrator():
    """Run latency benchmark."""
    print("\n" + "="*70)
    print("ORCHESTRATOR LATENCY BENCHMARK")
    print("="*70)
    
    case = create_sample_case()
    print(f"\nCase: {case.case_id}")
    print(f"  Claim: {case.claim.claim_id} (INPATIENT, $25k)")
    print(f"  Provider: NPI {case.provider.npi} (risk_score={case.provider.provider_risk_score})")
    
    # Benchmark with LLM reasoning enabled (parallelized)
    print("\n--- WITH LLM REASONING ENABLED (Parallelized) ---")
    orchestrator = Orchestrator(
        enable_llm_agent_reasoning=True,
        enable_genai_explanation=False,  # Disable explanation to isolate agent latency
    )
    
    start = time.time()
    result1 = orchestrator.investigate(case)
    elapsed_parallel = time.time() - start
    
    print(f"Total latency: {elapsed_parallel:.2f} seconds")
    print(f"  Selected agents: {result1.summary.get('selected_agents', [])}")
    print(f"  Failed agents: {result1.summary.get('failed_agents', [])}")
    print(f"  Risk score: {result1.investigation_risk_score}")
    print(f"  Findings count: {len(result1.findings)}")
    
    # Benchmark with LLM reasoning disabled (sequential, but simpler)
    print("\n--- WITH LLM REASONING DISABLED (Deterministic) ---")
    orchestrator2 = Orchestrator(
        enable_llm_agent_reasoning=False,
        enable_genai_explanation=False,
    )
    
    start = time.time()
    result2 = orchestrator2.investigate(case)
    elapsed_deterministic = time.time() - start
    
    print(f"Total latency: {elapsed_deterministic:.2f} seconds")
    print(f"  Selected agents: {result2.summary.get('selected_agents', [])}")
    print(f"  Failed agents: {result2.summary.get('failed_agents', [])}")
    print(f"  Risk score: {result2.investigation_risk_score}")
    print(f"  Findings count: {len(result2.findings)}")
    
    # Analysis
    print("\n" + "-"*70)
    print("LATENCY ANALYSIS")
    print("-"*70)
    if elapsed_parallel > 0:
        speedup = elapsed_deterministic / elapsed_parallel if elapsed_parallel > 0 else 1.0
        print(f"LLM latency:        {elapsed_parallel:.2f}s")
        print(f"Deterministic:      {elapsed_deterministic:.2f}s")
        print(f"Speedup factor:     {speedup:.2f}x")
        
        if speedup > 1.0:
            print(f"\n✓ Parallelization provides {((speedup-1)*100):.1f}% latency reduction")
        else:
            print(f"\n⚠ Deterministic is faster (no LLM overhead)")
    
    # Verify determinism
    print("\n--- DETERMINISM CHECK ---")
    if result1.investigation_risk_score == result2.investigation_risk_score:
        print(f"✓ Risk score is deterministic (frozen at {result1.investigation_risk_score})")
    else:
        print(f"✗ Risk score differs: LLM={result1.investigation_risk_score}, Det={result2.investigation_risk_score}")
    
    print("\n" + "="*70 + "\n")
    
    return {
        "case_id": case.case_id,
        "llm_latency_seconds": elapsed_parallel,
        "deterministic_latency_seconds": elapsed_deterministic,
        "risk_score_llm": result1.investigation_risk_score,
        "risk_score_deterministic": result2.investigation_risk_score,
        "findings_llm": len(result1.findings),
        "findings_deterministic": len(result2.findings),
    }


if __name__ == "__main__":
    benchmark_orchestrator()
