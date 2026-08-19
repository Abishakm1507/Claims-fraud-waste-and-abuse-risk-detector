import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 120000,
});

export const getOverview = () => client.get("/api/overview").then(r => r.data);
export const getFilters  = () => client.get("/api/filters").then(r => r.data);
export const getProviders = (params) =>
  client.get("/api/providers", { params }).then(r => r.data);
export const getClaims = (params) =>
  client.get("/api/claims", { params }).then(r => r.data);
export const getProviderCase = (npi, explain = true) =>
  client.get(`/api/investigate/provider/${npi}`, { params: { explain } }).then(r => r.data);
export const getClaimCase = (id, explain = true) =>
  client.get(`/api/investigate/claim/${encodeURIComponent(id)}`, { params: { explain } }).then(r => r.data);
/** Case report as a PDF blob. */
export const getReportPdf = (kind, id) =>
  client.get(`/api/report/${kind}/${encodeURIComponent(id)}`,
             { params: { format: "pdf" }, responseType: "blob" })
        .then(r => r.data);
export const getStatus = () => client.get("/api/status").then(r => r.data);
/** Ask a question. `context` carries the case from the previous turn so a
 *  follow-up resolves to it instead of resolving nothing. */
export const ask = (question, context) =>
  client.post("/api/chat", {
    question,
    context_entity: context?.id || null,
    context_kind: context?.kind || null,
  }).then(r => r.data);

/** Turn an axios failure into something the interface can act on. */
export function describeError(err) {
  if (err.code === "ECONNABORTED") return "The request timed out.";
  if (!err.response)
    return "Cannot reach the backend. Start it with: uvicorn backend.main:app --reload --port 8000";
  const d = err.response.data?.detail;
  if (typeof d === "string") return d;
  if (err.response.status === 503)
    return "The knowledge index is not built. Run: python scripts/build_index.py";
  return `Request failed (${err.response.status}).`;
}

/** Save a Blob to disk. Used for case report PDFs. */
export function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}
