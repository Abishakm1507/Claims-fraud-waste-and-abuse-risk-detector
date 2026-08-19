# FWA Investigation Workbench

Temporary React + Vite frontend shell for the healthcare claims FWA platform. It consumes the existing FastAPI contracts and keeps API calls in `src/api/client.js` so the eventual frontend can replace the presentation layer without changing backend code.

## Run

Start the backend from the repository root:

```powershell
uvicorn backend.main:app --reload --port 8732
```

Then start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5193. Set `VITE_API_BASE_URL` when the backend is not available through the Vite proxy.

## Routes

- `#/dashboard` loads portfolio statistics and live claim/provider investigation queues.
- `#/claim-investigation` runs the combined claim investigation contract.
- `#/provider-investigation` loads provider risk, evidence, peer context, LEIE data, and linked claims.
- The floating RAG assistant is available on every route.

## Backend endpoints consumed

- `GET /api/v1/stats/overview`
- `GET /api/v1/claims`
- `GET /api/v1/claims/{claim_id}`
- `POST /api/v1/investigations/{case_id}/run`
- `GET /api/v1/providers`
- `GET /api/v1/providers/{npi}`
- `GET /api/v1/reports/{case_id}`
- `POST /api/chat`
- `GET /api/status`

The provider API currently exposes provider risk and evidence but does not expose provider-level SHAP or GenAI narrative fields. The provider screen labels those fields as unavailable rather than inventing values.
