from multi_agent.orchestrator import Orchestrator
from multi_agent.rag.handoff import build_rag_handoff
from multi_agent.data.claim_store import ClaimStore

# Get a real claim
store = ClaimStore()
df = store._df
carrier = df[df['CLAIM_TYPE'] == 'CARRIER'].dropna(subset=['CLAIM_ID']).iloc[0]
claim_id = str(carrier['CLAIM_ID'])

print("=== DOWNSTREAM CONSUMER TEST: RAG HANDOFF ===\n")
print(f"Testing with claim_id: {claim_id}\n")

# Run investigation
result = Orchestrator(enable_genai_explanation=False, enable_llm_agent_reasoning=False).investigate_claim(claim_id)

print(f"Investigation result:")
print(f"  case_id: {result.case_id}")
print(f"  investigation_risk_score: {result.investigation_risk_score}")
print(f"  findings_count: {result.summary.get('total_findings')}\n")

# Build RAG handoff
try:
    rag_data = build_rag_handoff(result)
    print(f"RAG handoff built successfully:")
    print(f"  case_id: {rag_data.case.case_id}")
    print(f"  claim_id: {rag_data.case.claim_id}")
    print(f"  findings_count: {len(rag_data.findings)}")
    print(f"  agent_results_count: {len(rag_data.agent_results)}")
    print(f"  risk_synthesis.overall_risk: {rag_data.risk_synthesis.overall_risk}")
    print(f"  risk_synthesis.risk_category: {rag_data.risk_synthesis.risk_category.value}")
    print(f"\n✓ RAG handoff consumer verified successfully")
except Exception as e:
    print(f"✗ RAG handoff failed: {e}")
    import traceback
    traceback.print_exc()
