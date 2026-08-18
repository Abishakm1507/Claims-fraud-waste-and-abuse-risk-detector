import os
import time
from dotenv import load_dotenv

load_dotenv()

from multi_agent.orchestrator import Orchestrator
from multi_agent.data.claim_store import ClaimStore

print('=== ENVIRONMENT ===')
print('groq_api_key_configured:', bool(os.getenv('GROQ_API_KEY')))
print('groq_model:', os.getenv('GROQ_MODEL', 'N/A'))

print('\n=== REAL INVESTIGATION WITH LLM ===')

# Get a real claim to investigate
store = ClaimStore()
df = store._df
carrier = df[df['CLAIM_TYPE'] == 'CARRIER'].dropna(subset=['CLAIM_ID']).iloc[0]
claim_id = str(carrier['CLAIM_ID'])
claim_type = carrier['CLAIM_TYPE']

print('claim_id:', claim_id)
print('claim_type:', claim_type)

# Run with both LLM and Groq enabled
orch = Orchestrator(enable_llm_agent_reasoning=True, enable_genai_explanation=True)

start = time.perf_counter()
result = orch.investigate_claim(claim_id)
elapsed = time.perf_counter() - start

print('\n=== RESULTS ===')
print('case_id:', result.case_id)
print('investigation_risk_score:', result.investigation_risk_score)
print('investigation_priority:', result.investigation_priority)
print('total_findings:', result.summary.get('total_findings'))
print('selected_agents:', result.summary.get('selected_agents'))
print('explanation_status:', result.summary.get('explanation_status'))
print('explanation_error:', result.summary.get('explanation_error', ''))
print('genai_model:', result.summary.get('genai_model'))

print('\n=== TIMING ===')
diag = result.diagnostic_timing.get('orchestrator_total_seconds')
print('orchestrator_total_seconds:', f'{diag:.4f}' if diag else 'N/A')
print('total_wall_elapsed:', f'{elapsed:.4f}')

print('\n=== GENAI EXPLANATION (truncated) ===')
if result.explanation:
    print(result.explanation[:200] + ('...' if len(result.explanation) > 200 else ''))
else:
    print('(no explanation)')

print('\n=== ROUTING ===')
for agent, route in result.summary.get('routing', {}).items():
    reason_snippet = route.get("reason", "")[:50] if route.get("reason") else ""
    print(f'{agent}: selected={route.get("selected")}, status={route.get("status")}, reason={reason_snippet}')
