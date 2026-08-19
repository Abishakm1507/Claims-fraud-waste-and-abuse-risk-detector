from backend.app.data.repository import repository
from fastapi.testclient import TestClient
from backend.main import app
import json

client = TestClient(app)

# Get one claim from each type
carrier = repository.claims_df[repository.claims_df['claim_type'] == 'CARRIER'].iloc[0]['claim_id']
inpatient = repository.claims_df[repository.claims_df['claim_type'] == 'INPATIENT'].iloc[0]['claim_id']
outpatient = repository.claims_df[repository.claims_df['claim_type'] == 'OUTPATIENT'].iloc[0]['claim_id']

for claim_type, claim_id in [('CARRIER', carrier), ('INPATIENT', inpatient), ('OUTPATIENT', outpatient)]:
    response = client.get(f'/api/v1/claims/{claim_id}')
    if response.status_code == 200:
        data = response.json()
        ml_ev = data.get('ml_evidence', {})
        print(f'\n{claim_type} Claim {claim_id}:')
        print(f'  Ensemble Score: {ml_ev.get("ensemble_score", "N/A")}')
        print(f'  Risk Band: {ml_ev.get("risk_band", "N/A")}')
        print(f'  Risk Rank: {ml_ev.get("risk_rank", "N/A")}')
        print(f'  Model Scores: {ml_ev.get("model_scores", {})}')
        print(f'  Consensus: {ml_ev.get("model_consensus", "N/A")}')
        print(f'  Consensus Count: {ml_ev.get("model_consensus_count", "N/A")}')
        print(f'  Feature Evidence Count: {len(ml_ev.get("feature_evidence", {}))}')
