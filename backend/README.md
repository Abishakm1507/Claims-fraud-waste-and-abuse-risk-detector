# Backend API

This backend exposes the investigation queue, claim detail/report endpoints, and provider evidence surface for the FWA detector.

## Local run

From the repo root:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Parquet engine note

The provider parquet files in `data/interim/` are read with `fastparquet`, not `pyarrow`, because `pyarrow` is not compatible with the way these files were written in this repo. The practical root cause is not a corrupted dataset: the parquet schema is readable and valid, but the file metadata/serialization layout is one that `fastparquet` handles successfully while `pyarrow` rejects in this environment. We intentionally pin `fastparquet` in `requirements.txt` so a fresh setup does not trigger the same debugging loop.

The backend config and tests are also designed to reuse the shared repository singleton instead of reloading the full data stack per test, which keeps the suite fast and avoids repeated disk I/O across the entire session.

## Health and docs

- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json
- App root: http://localhost:8000/

## Core endpoints

- GET /api/v1/health
- GET /api/v1/stats/overview
- GET /api/v1/claims
- GET /api/v1/claims/{claim_id}
- GET /api/v1/providers
- GET /api/v1/providers/{npi}
- POST /api/v1/investigations/{case_id}/run
- GET /api/v1/reports/{case_id}
- POST /api/v1/chat

## Contract notes

- Claim list responses use a lean `ml_evidence` payload without the full feature vector.
- Claim detail and report responses include the full ML evidence block with `feature_evidence` preserved.
- Provider responses now include `provider_evidence` for LEIE exclusion status, peer benchmark comparison, and datasource provenance.
- The backend is intentionally stubbed for multi-agent and explainability services, but the HTTP contract remains stable.

## Current data contract

The backend is built around the real repo artifacts:

- claims: models/claims/final_unified_claim_risk.csv
- provider risk file: models/provider/provider_risk_scores.csv
- provider evidence parquet sources:
  - data/interim/leie_clean.parquet
  - data/interim/provider_service_clean.parquet
  - data/interim/geo_benchmark_clean.parquet

The repository validates type coverage and integrity at startup, and the service is designed to fail safely when data is missing.
