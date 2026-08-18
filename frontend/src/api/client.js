import axios from "axios";

// Empty base URL means requests go to /api on the same origin, which the Vite
// dev proxy forwards to the backend. Set VITE_API_BASE_URL to point elsewhere.
const baseURL = import.meta.env.VITE_API_BASE_URL || "";

const client = axios.create({
  baseURL,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

/** Ask the assistant a question. Returns the full response contract. */
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
