import axios from "axios";

// Empty base URL means requests go to /api on the same origin, which the Vite
// dev proxy forwards to the backend. Set VITE_API_BASE_URL to point elsewhere.
const baseURL = import.meta.env.VITE_API_BASE_URL || "";

const client = axios.create({
  baseURL,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

const api = axios.create({
  baseURL,
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

export async function getOverview() {
  const { data } = await api.get("/api/v1/stats/overview");
  return data;
}

export async function getClaims(params = {}) {
  const { data } = await api.get("/api/v1/claims", { params });
  return data;
}

export async function getProviders(params = {}) {
  const { data } = await api.get("/api/v1/providers", { params });
  return data;
}

export async function getClaim(claimId) {
  const { data } = await api.get(`/api/v1/claims/${encodeURIComponent(claimId)}`);
  return data;
}

export async function runClaimInvestigation(claimId) {
  const { data } = await api.post(`/api/v1/investigations/${encodeURIComponent(claimId)}/run`);
  return data;
}

export async function getProvider(npi) {
  const { data } = await api.get(`/api/v1/providers/${encodeURIComponent(npi)}`);
  return data;
}

export async function getReport(caseId) {
  const { data } = await api.get(`/api/v1/reports/${encodeURIComponent(caseId)}`);
  return data;
}

export async function downloadReport(caseId) {
  const report = await getReport(caseId);
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = report.download?.filename || `report-${caseId}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  return report;
}

/** Ask the real RAG assistant. Returns the complete response contract. */
export async function askQuestion(question, topK = 5) {
  const { data } = await client.post("/api/chat", {
    question,
    top_k: topK,
  });
  return data;
}

/** Source connection status. Available for debugging; the UI does not use it. */
export async function fetchStatus() {
  const { data } = await client.get("/api/status");
  return data;
}

/** Turn an axios failure into something an investigator can act on. */
export function describeError(error) {
  if (error.code === "ECONNABORTED") {
    return "The request timed out. The backend may still be starting up.";
  }
  if (!error.response) {
    return "Cannot reach the backend. Start it with: uvicorn backend.main:app --reload --port 8732";
  }
  const detail = error.response.data?.detail;
  if (typeof detail === "string") return detail;
  if (error.response.status === 503) {
    return "The knowledge index is not built. Run: python scripts/build_index.py";
  }
  return `Request failed (${error.response.status}).`;
}
