# Backend API Contract

Version: 1.0.0
Published: 2026-08-18

This contract describes the stable HTTP surface exposed by the FastAPI app in this repository.

## Base URL

- http://localhost:8000/api/v1

## OpenAPI source

The canonical schema is generated from the FastAPI app and is available at:

- http://localhost:8000/docs
- http://localhost:8000/openapi.json

## Endpoints

### GET /api/v1/health

Returns startup status and row counts for the loaded datasets.

Example:

```json
{
  "status": "ok",
  "service": "claims-fwa-risk-api",
  "data_loaded": {
    "claims": 65941,
    "providers": 2368
  }
}
```

### GET /api/v1/stats/overview

Returns overall risk numbers and a per-claim-type breakdown.

Example keys:

- total_claims
- total_providers
- high_risk_claims
- high_risk_providers
- risk_distribution
- provider_risk_distribution
- top_risk_factors
- per_claim_type

### GET /api/v1/claims

Query params:

- claim_type: CARRIER | INPATIENT | OUTPATIENT
- risk_band: LOW | MEDIUM | HIGH | CRITICAL
- provider: provider ID / NPI filter
- date_from, date_to: ISO-like date filters
- sort_by: default claim_risk_score
- order: asc | desc
- page: page number (>=1)
- page_size: 1-200

Returns paginated claim rows with lean `ml_evidence`.

Example:

```json
{
  "items": [
    {
      "claim_id": "C123",
      "claim_type": "CARRIER",
      "provider_id": "1003078684",
      "claim_risk_score": 80.5,
      "risk_level": "HIGH",
      "ml_evidence": {
        "claim_type": "CARRIER",
        "ensemble_score": 84.1,
        "risk_band": "HIGH"
      }
    }
  ],
  "page": 1,
  "page_size": 25,
  "total": 65941,
  "total_pages": 2638
}
```

### GET /api/v1/claims/{claim_id}

Returns full claim detail, provider context, ML evidence, investigation stub, and explanation block.

Important fields:

- claim
- provider
- ml_evidence
- investigation
- shap
- genai_narrative
- recommendation
- risk_summary

`ml_evidence` is the full evidence object including feature data for a single claim.

### GET /api/v1/providers

Query params:

- risk_band: provider risk band
- state: provider state code
- sort_by: default provider_risk_score
- order: asc | desc
- page, page_size

Example provider item fields:

- npi
- provider_type
- state
- provider_risk_score
- provider_risk_level
- top_risk_reasons
- provider_evidence

`provider_evidence` contains:

```json
{
  "exclusion_status": "EXCLUDED",
  "peer_percentile": 69.93,
  "leie_match": true,
  "service_row_count": 125,
  "source_files": [
    "data\\interim\\leie_clean.parquet",
    "data\\interim\\provider_service_clean.parquet",
    "data\\interim\\geo_benchmark_clean.parquet"
  ]
}
```

### GET /api/v1/providers/{npi}

Returns the provider record plus claims linked to that NPI and a single top-level `provider_evidence` payload.

Important fields:

- provider
- provider_evidence
- claims
- investigation

Example response for an excluded provider (`1003078684`):

```json
{
  "provider": {
    "npi": "1003078684",
    "provider_type": "Family Practice",
    "state": "FL",
    "provider_risk_score": 16.03,
    "provider_risk_level": "LOW",
    "top_risk_reasons": "unusually high 5-year average total payment (z=18.5 vs. population median); unusually high 5-year average total services (z=12.4 vs. population median); unusually high services-per-beneficiary deviation from specialty peers (z=6.6 vs. population median)"
  },
  "provider_evidence": {
    "npi": "1003078684",
    "provider_type": "Family Practice",
    "state": "FL",
    "exclusion_status": "EXCLUDED",
    "leie_match": {
      "exclusion_type": "1128B4",
      "exclusion_date": "2026-04-20T00:00:00",
      "reinstatement_date": null,
      "waiver_date": null,
      "state": "PA",
      "specialty": "FAMILY PRACTICE",
      "business_name": null,
      "is_individual": true
    },
    "peer_benchmark": {
      "service_row_count": 125,
      "avg_allowed_amount": 101.48,
      "avg_payment_amount": 80.88,
      "total_services": 27486.0,
      "year_coverage": [2020, 2021, 2022, 2023, 2024],
      "peer_percentile": 69.93,
      "peer_comparison_basis": {
        "provider_type": "Family Practice",
        "state": "FL",
        "peer_population_count": 14
      },
      "geo_benchmark_matches": 22,
      "geo_benchmark_years": [2020, 2021, 2022, 2023, 2024]
    },
    "service_summary": {
      "total_services": 27486.0,
      "avg_allowed_amount": 101.48,
      "avg_payment_amount": 80.88,
      "provider_specialty": "Family Practice",
      "provider_state": "FL"
    },
    "provenance": {
      "leie_match": true,
      "has_service_rows": true,
      "has_geo_benchmark_rows": true
    },
    "source_files": [
      "data\\interim\\leie_clean.parquet",
      "data\\interim\\provider_service_clean.parquet",
      "data\\interim\\geo_benchmark_clean.parquet"
    ]
  },
  "claims": [],
  "investigation": {
    "provider_npi": "1003078684",
    "provider_risk_score": 16.03,
    "risk_level": "LOW",
    "related_claim_count": 0,
    "recommendation": "Review billing patterns and peer utilization deviations before dismissal."
  }
}
```

Example response for a non-excluded provider (`1003000134`):

```json
{
  "provider": {
    "npi": "1003000134",
    "provider_type": "Pathology",
    "state": "IL",
    "provider_risk_score": 10.91,
    "provider_risk_level": "LOW",
    "top_risk_reasons": "unusually high 5-year average total services (z=12.0 vs. population median); unusually high 5-year average total payment (z=4.4 vs. population median); unusually high total beneficiaries served (z=4.1 vs. population median)"
  },
  "provider_evidence": {
    "npi": "1003000134",
    "provider_type": "Pathology",
    "state": "IL",
    "exclusion_status": "NOT_FOUND",
    "leie_match": null,
    "peer_benchmark": {
      "service_row_count": 59,
      "avg_allowed_amount": 37.42,
      "avg_payment_amount": 28.96,
      "total_services": 26684.0,
      "year_coverage": [2020, 2021, 2022, 2023, 2024],
      "peer_percentile": 57.69,
      "peer_comparison_basis": {
        "provider_type": "Pathology",
        "state": "IL",
        "peer_population_count": 7
      },
      "geo_benchmark_matches": 15,
      "geo_benchmark_years": [2020, 2021, 2022, 2023, 2024]
    },
    "service_summary": {
      "total_services": 26684.0,
      "avg_allowed_amount": 37.42,
      "avg_payment_amount": 28.96,
      "provider_specialty": "Pathology",
      "provider_state": "IL"
    },
    "provenance": {
      "leie_match": false,
      "has_service_rows": true,
      "has_geo_benchmark_rows": true
    },
    "source_files": [
      "data\\interim\\provider_service_clean.parquet",
      "data\\interim\\geo_benchmark_clean.parquet"
    ]
  },
  "claims": [],
  "investigation": {
    "provider_npi": "1003000134",
    "provider_risk_score": 10.91,
    "risk_level": "LOW",
    "related_claim_count": 0,
    "recommendation": "Review billing patterns and peer utilization deviations before dismissal."
  }
}
```

### POST /api/v1/investigations/{case_id}/run

Starts an investigation run for the given case ID.

Example response:

```json
{
  "case_id": "C123",
  "status": "started",
  "investigation": {},
  "message": "Investigation run triggered through the backend stub orchestration contract."
}
```

### GET /api/v1/reports/{case_id}

Returns the investigation report with the same full ML evidence and report payloads used for auditability.

### POST /api/v1/chat

Stubbed RAG chat endpoint.

Request body:

```json
{
  "message": "hello",
  "case_id": "CASE-123"
}
```

Response:

```json
{
  "status": "stub",
  "response": "Stubbed RAG response for case CASE-123: ...",
  "case_id": "CASE-123"
}
```

## Error envelope

All request errors use the same envelope:

```json
{
  "error": {
    "code": "CLAIM_NOT_FOUND",
    "message": "Claim ... not found"
  }
}
```

## Contract guarantees

- The backend is intended to stay backward-compatible for the existing HTTP contract while real multi-agent and explainability services are introduced behind the current interfaces.
- List endpoints are intentionally lean for queue performance.
- Detail and report endpoints remain full and auditable.
- Provider evidence is preserved as normalized metadata rather than being flattened into a single score.

## Known current stubs

- Investigation orchestration is a backend stub.
- Explainability and RAG output are stubbed.
- The underlying ML claim evidence is served from finalized CSV artifacts, not live model inference.
