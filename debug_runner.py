from multi_agent.data.claim_store import ClaimStore
from multi_agent.orchestrator import Orchestrator

print('start')
store = ClaimStore()
print('store loaded', len(store._df))
df = store._df
row = df[(df['CLAIM_TYPE']=='CARRIER') & (df['PROVIDER_ID_TYPE']=='NPI')].dropna(subset=['CLAIM_ID']).iloc[0]
print('row loaded', row['CLAIM_ID'])
claim = store.get_claim(str(row['CLAIM_ID']))
print('claim loaded', claim.claim_id, claim.provider_id, claim.provider_id_type)
print('before investigate')
result = Orchestrator().investigate_claim(claim.claim_id)
print('after investigate', result.case_id, result.summary['total_findings'], result.routing['peer'])
