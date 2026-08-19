import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  describeError, downloadReport, getClaim, getClaims, getOverview,
  getProvider, getProviders, runClaimInvestigation,
} from "./api/client.js";
import FloatingRagChatbot from "./components/FloatingRagChatbot.jsx";

const NAV = [
  ["dashboard", "Dashboard", "Overview"],
  ["claim-investigation", "Claim Investigation", "Claim"],
  ["provider-investigation", "Provider Investigation", "Provider"],
];

function readRoute() {
  const raw = window.location.hash.replace(/^#\/?/, "") || "dashboard";
  const [path, query] = raw.split("?");
  return { path, params: new URLSearchParams(query || "") };
}

function go(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  window.location.hash = `/${path}${query ? `?${query}` : ""}`;
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "Not available";
  return typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : String(value);
}

function riskTone(value) { return String(value || "unknown").toLowerCase(); }
function riskLabel(value) { return String(value || "Not available").replaceAll("_", " "); }
function getCase(data) { return data?.investigation?.case || data?.investigation || data?.case || data; }

function ErrorState({ message, onRetry }) {
  return <div className="state error-state"><strong>Could not load this view</strong><span>{message}</span>{onRetry && <button className="button secondary" onClick={onRetry}>Retry</button>}</div>;
}
function LoadingState({ label = "Loading live backend data..." }) { return <div className="state"><span className="spinner" />{label}</div>; }
function EmptyState({ children = "Enter an identifier to begin an investigation." }) { return <div className="state empty-state"><strong>No investigation loaded</strong><span>{children}</span></div>; }
function Badge({ value }) { return <span className={`badge ${riskTone(value)}`}>{riskLabel(value)}</span>; }
function StatCard({ label, value, detail, accent = "blue" }) { return <article className={`stat-card ${accent}`}><span className="eyebrow">{label}</span><strong>{formatNumber(value, 0)}</strong>{detail && <small>{detail}</small>}</article>; }
function Section({ title, eyebrow, action, children, className = "" }) { return <section className={`section ${className}`}><div className="section-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>{action}</div>{children}</section>; }
function KeyValue({ label, value }) { if (value === null || value === undefined || value === "") return null; return <div className="key-value"><span>{label}</span><strong>{typeof value === "object" ? JSON.stringify(value) : String(value)}</strong></div>; }

function RiskScore({ score, level, label = "Overall risk" }) {
  const numeric = Number(score); const width = Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : 0;
  return <div className="risk-score"><div className="score-heading"><span>{label}</span><strong>{Number.isFinite(numeric) ? `${formatNumber(numeric)} / 100` : "Not available"}</strong></div><div className="score-track"><span className={`score-fill ${riskTone(level)}`} style={{ width: `${width}%` }} /></div>{level && <Badge value={level} />}</div>;
}

function DataList({ items, empty = "No data returned by the backend." }) {
  if (!items?.length) return <p className="muted">{empty}</p>;
  return <div className="data-list">{items.map((item, index) => <div className="data-row" key={item.evidence_id || item.finding_id || item.execution_id || index}><div><strong>{item.title || item.metric || item.name || item.finding || item.category || "Evidence"}</strong>{item.description && <span>{item.description}</span>}{item.source && <small>Source: {item.source}</small>}</div>{(item.severity || item.risk || item.status) && <Badge value={item.severity || item.risk || item.status} />}</div>)}</div>;
}

function InvestigationStages({ loading, limited }) {
  return <div className="stage-strip">{["ML risk analysis", "Multi-agent investigation", "Evidence synthesis", "Explainability"].map((stage, index) => <div className={`stage ${loading ? "active" : "complete"}`} key={stage}><span>{index + 1}</span>{stage}</div>)}{limited && <p className="notice">Investigation completed with limited GenAI explanation because the LLM service is temporarily rate-limited.</p>}</div>;
}

function Dashboard() {
  const [data, setData] = useState(null); const [error, setError] = useState("");
  const load = () => { setError(""); Promise.all([getOverview(), getClaims({ page: 1, page_size: 8 }), getProviders({ page: 1, page_size: 8 })]).then(([overview, claims, providers]) => setData({ overview, claims, providers })).catch((err) => setError(describeError(err))); };
  useEffect(load, []);
  if (error) return <PageFrame title="Dashboard"><ErrorState message={error} onRetry={load} /></PageFrame>;
  if (!data) return <PageFrame title="Dashboard"><LoadingState /></PageFrame>;
  const { overview, claims, providers } = data;
  return <PageFrame title="Dashboard" subtitle="Live portfolio view across claims, providers, and investigation queues."><div className="stat-grid"><StatCard label="Total claims" value={overview.total_claims} detail="Loaded dataset" /><StatCard label="Total providers" value={overview.total_providers} detail="Provider population" accent="green" /><StatCard label="High-risk claims" value={overview.high_risk_claims} detail="High and critical" accent="amber" /><StatCard label="High-risk providers" value={overview.high_risk_providers} detail="High and critical" accent="red" /></div><div className="dashboard-grid"><Section title="Risk distribution" eyebrow="Claims portfolio"><Distribution values={overview.risk_distribution} /></Section><Section title="Anomaly distribution" eyebrow="Claim types"><Distribution values={overview.per_claim_type} nested /></Section><Section title="Top risk factors" eyebrow="Model signals"><DataList items={overview.top_risk_factors?.map((item) => typeof item === "string" ? { name: item } : item)} /></Section></div><Section title="Investigation queue" eyebrow="Priority work" className="queue-section"><div className="queue-grid"><RiskTable title="Top risk claims" type="claim" rows={claims.items || []} /><RiskTable title="Top risk providers" type="provider" rows={providers.items || []} /></div></Section></PageFrame>;
}

function Distribution({ values, nested }) {
  const entries = Object.entries(values || {}).flatMap(([key, value]) => nested && value?.risk_band_distribution ? Object.entries(value.risk_band_distribution).map(([band, count]) => [`${key} ${band}`, count]) : [[key, value]]); const max = Math.max(...entries.map(([, value]) => Number(value) || 0), 1);
  return <div className="distribution">{entries.slice(0, nested ? 12 : 8).map(([label, value]) => <div className="distribution-row" key={label}><div><span>{riskLabel(label)}</span><strong>{formatNumber(value, 0)}</strong></div><div className="bar"><span style={{ width: `${(Number(value) / max) * 100}%` }} /></div></div>)}</div>;
}

function RiskTable({ title, type, rows }) {
  return <div className="table-wrap"><div className="table-title"><h3>{title}</h3><span>{rows.length} shown</span></div><table><thead><tr>{type === "claim" ? <><th>Claim ID</th><th>Type</th><th>Score</th><th>Risk</th><th>Provider</th></> : <><th>Provider / NPI</th><th>Score</th><th>Risk</th><th>State</th></>}<th /></tr></thead><tbody>{rows.map((row) => <tr key={row.claim_id || row.npi}>{type === "claim" ? <><td className="mono">{row.claim_id}</td><td>{row.claim_type}</td><td>{formatNumber(row.claim_risk_score ?? row.ml_evidence?.ensemble_score)}</td><td><Badge value={row.risk_level || row.ml_evidence?.risk_band} /></td><td className="mono">{row.provider_id || "Not available"}</td></> : <><td className="mono">{row.npi}</td><td>{formatNumber(row.provider_risk_score)}</td><td><Badge value={row.provider_risk_level} /></td><td>{row.state || "Not available"}</td></>}<td><button className="button tiny" onClick={() => go(type === "claim" ? "claim-investigation" : "provider-investigation", { id: type === "claim" ? row.claim_id : row.npi })}>Investigate</button></td></tr>)}</tbody></table>{!rows.length && <p className="muted">No queue items returned by the backend.</p>}</div>;
}

function LookupForm({ value, onChange, onSubmit, placeholder, label, button }) { return <form className="lookup-form" onSubmit={onSubmit}><label><span className="eyebrow">{label}</span><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label><button className="button primary" type="submit">{button}</button></form>; }

function ClaimInvestigation({ initialId }) {
  const [claimId, setClaimId] = useState(initialId || ""); const [data, setData] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [limited, setLimited] = useState(false);
  const investigate = async (event) => { event?.preventDefault(); const id = claimId.trim(); if (!id) return; setLoading(true); setError(""); setData(null); setLimited(false); try { await runClaimInvestigation(id); setData(await getClaim(id)); } catch (err) { const message = describeError(err); setLimited(/rate.limit|groq|limited genai/i.test(message)); setError(message); } finally { setLoading(false); } };
  useEffect(() => { if (initialId) investigate(); }, [initialId]);
  return <PageFrame title="Claim Investigation" subtitle="Trace a claim from model signal through evidence, agents, and explanation."><LookupForm value={claimId} onChange={setClaimId} onSubmit={investigate} placeholder="Enter claim ID" label="Claim ID" button="Investigate Claim" />{loading && <><InvestigationStages loading /><LoadingState label="Running the combined investigation contract..." /></>}{error && <ErrorState message={error} onRetry={investigate} />}{!loading && !error && !data && <EmptyState />}{data && <ClaimResult data={data} limited={limited} />}</PageFrame>;
}

function ClaimResult({ data, limited }) {
  const caseData = getCase(data); const risk = data.risk_summary || caseData.risk_synthesis || {}; const agents = caseData.agent_results || []; const findings = caseData.findings || [];
  return <div className="result-stack"><InvestigationStages limited={limited} /><div className="result-header"><div><span className="eyebrow">Investigation result</span><h2>{data.claim?.claim_id || caseData.claim_id}</h2><p className="muted">{data.claim?.claim_type || caseData.claim_type} claim linked to provider {data.claim?.provider_id || caseData.provider_id || "Not available"}</p></div><button className="button secondary" onClick={() => downloadReport(data.claim?.claim_id || caseData.case_id)}>Download Investigation Report</button></div><div className="overview-grid"><InfoCard title="Claim overview"><KeyValue label="Claim ID" value={data.claim?.claim_id || caseData.claim_id} /><KeyValue label="Provider ID" value={data.claim?.provider_id || caseData.provider_id} /><KeyValue label="Claim type" value={data.claim?.claim_type || caseData.claim_type} /><KeyValue label="Status" value="Completed" /></InfoCard><InfoCard title="Risk profile"><RiskScore score={risk.overall_risk ?? data.claim?.claim_risk_score} level={risk.risk_category || data.claim?.risk_level} /><KeyValue label="Priority" value={risk.priority} /></InfoCard></div><Section title="Multi-agent findings" eyebrow="Investigation evidence"><div className="agent-grid">{agents.map((agent) => <InfoCard key={agent.agent} title={agent.agent}><KeyValue label="Status" value={agent.status} /><KeyValue label="Score" value={agent.score} /><DataList items={agent.findings} /><DataList items={agent.evidence} /></InfoCard>)}{!agents.length && <DataList items={findings} />}</div></Section><div className="two-column"><Section title="Evidence" eyebrow="Traceable inputs"><DataList items={caseData.evidence} /></Section><Section title="SHAP explainability" eyebrow="Model contribution"><FeatureList features={data.shap?.top_features} /></Section></div><Explanation data={data.genai_narrative} recommendation={data.recommendation} /></div>;
}

function ProviderInvestigation({ initialId }) {
  const [npi, setNpi] = useState(initialId || ""); const [data, setData] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const investigate = async (event) => { event?.preventDefault(); const id = npi.trim(); if (!id) return; setLoading(true); setError(""); setData(null); try { setData(await getProvider(id)); } catch (err) { setError(describeError(err)); } finally { setLoading(false); } };
  useEffect(() => { if (initialId) investigate(); }, [initialId]);
  return <PageFrame title="Provider Investigation" subtitle="Review provider risk, peer benchmarks, exclusions, and linked claim activity."><LookupForm value={npi} onChange={setNpi} onSubmit={investigate} placeholder="Enter NPI or provider ID" label="NPI / Provider ID" button="Investigate Provider" />{loading && <LoadingState label="Loading provider risk and evidence..." />}{error && <ErrorState message={error} onRetry={investigate} />}{!loading && !error && !data && <EmptyState />}{data && <ProviderResult data={data} />}</PageFrame>;
}

function ProviderResult({ data }) {
  const provider = data.provider || {}; const evidence = data.provider_evidence || {}; const investigation = data.investigation || {}; const peer = evidence.peer_benchmark || {}; const summary = evidence.service_summary || {};
  return <div className="result-stack"><div className="result-header"><div><span className="eyebrow">Provider investigation</span><h2>{provider.npi}</h2><p className="muted">{provider.provider_type || "Provider type not available"} · {provider.state || "Location not available"}</p></div><span className={`badge ${riskTone(investigation.risk_level || provider.provider_risk_level)}`}>{riskLabel(investigation.risk_level || provider.provider_risk_level)}</span></div><div className="overview-grid"><InfoCard title="Provider overview"><KeyValue label="NPI" value={provider.npi} /><KeyValue label="Specialty" value={provider.provider_type} /><KeyValue label="Location" value={provider.state} /><KeyValue label="Exclusion" value={evidence.exclusion_status} /><KeyValue label="Linked claims" value={investigation.related_claim_count} /></InfoCard><InfoCard title="Risk profile"><RiskScore score={provider.provider_risk_score} level={provider.provider_risk_level} label="Provider risk score" /><KeyValue label="Investigation status" value="Completed" /></InfoCard></div><Section title="Provider evidence" eyebrow="Available backend facts"><DataList items={Object.entries({ ...summary, ...peer, ...evidence.provenance }).map(([name, value]) => ({ name: name.replaceAll("_", " "), description: typeof value === "object" ? JSON.stringify(value) : String(value) }))} /></Section><div className="two-column"><Section title="Peer comparison" eyebrow="Comparable provider context"><div className="comparison"><div><span className="eyebrow">Investigated provider</span><strong>{provider.npi}</strong><KeyValue label="Peer percentile" value={peer.peer_percentile} /><KeyValue label="Total services" value={summary.total_services || peer.total_services} /><KeyValue label="Avg payment" value={summary.avg_payment_amount || peer.avg_payment_amount} /></div><div><span className="eyebrow">Comparable providers</span><strong>{peer.peer_comparison_basis?.peer_population_count ? `${peer.peer_comparison_basis.peer_population_count} in peer group` : "Not available"}</strong><KeyValue label="Peer basis" value={peer.peer_comparison_basis?.provider_type} /><KeyValue label="State" value={peer.peer_comparison_basis?.state} /></div></div></Section><Section title="LEIE and rule signals" eyebrow="Clinical / compliance context"><KeyValue label="Exclusion status" value={evidence.exclusion_status} /><DataList items={evidence.leie_match ? Object.entries(evidence.leie_match).map(([name, value]) => ({ name: name.replaceAll("_", " "), description: String(value) })) : []} empty="No LEIE match returned by the backend." /></Section></div><Explanation data={null} recommendation={investigation.recommendation} note="The provider endpoint currently returns provider risk and evidence, but no provider-level SHAP or GenAI narrative contract." /><Section title="Linked claims" eyebrow="Claims associated with this provider"><RiskTable title="Claims" type="claim" rows={(data.claims || []).slice(0, 25)} /></Section></div>;
}

function InfoCard({ title, children }) { return <article className="info-card"><h3>{title}</h3>{children}</article>; }
function FeatureList({ features }) { return <div className="feature-list">{features?.length ? features.map((feature) => <div className="feature" key={feature.name}><div><strong>{feature.name}</strong><span>{feature.direction || (Number(feature.importance) >= 0 ? "Positive contribution" : "Negative contribution")}</span></div><strong>{formatNumber(feature.importance ?? feature.contribution, 3)}</strong></div>) : <p className="muted">No SHAP features were returned.</p>}</div>; }
function Explanation({ data, recommendation, note }) { const summary = data?.summary || data?.investigation_narrative || data?.executive_summary; return <Section title="Explanation and recommendation" eyebrow="Decision support"><div className="explanation">{note && <p className="notice">{note}</p>}{summary ? <ReactMarkdown>{summary}</ReactMarkdown> : <p className="muted">No GenAI narrative was returned. Deterministic evidence remains authoritative.</p>}{data?.key_findings?.length > 0 && <><h3>Key findings</h3><DataList items={data.key_findings.map((item) => ({ name: item.finding || item.title, description: item.evidence_ids?.join(", ") }))} /></>}{data?.limitations?.length > 0 && <p className="notice">Limitations: {data.limitations.join(" ")}</p>}<h3>Recommendation</h3><p>{recommendation || "No recommendation was returned by the backend."}</p></div></Section>; }

function PageFrame({ title, subtitle, children }) { return <main className="main-content"><div className="page-heading"><div><span className="eyebrow">Healthcare FWA workbench</span><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div><span className="live-indicator"><i /> Backend connected on demand</span></div>{children}</main>; }

function App() {
  const [route, setRoute] = useState(readRoute());
  useEffect(() => { const onHash = () => setRoute(readRoute()); window.addEventListener("hashchange", onHash); return () => window.removeEventListener("hashchange", onHash); }, []);
  const page = useMemo(() => { if (route.path === "claim-investigation") return <ClaimInvestigation initialId={route.params.get("id")} />; if (route.path === "provider-investigation") return <ProviderInvestigation initialId={route.params.get("id")} />; return <Dashboard />; }, [route]);
  return <div className="app-shell"><aside className="app-sidebar"><div className="brand"><span className="brand-mark">FWA</span><div><strong>Risk Desk</strong><small>Investigation platform</small></div></div><nav>{NAV.map(([path, label, short]) => <button className={route.path === path ? "active" : ""} key={path} onClick={() => go(path)}><span>{short}</span>{label}</button>)}</nav><div className="sidebar-footer"><span>Live data source</span><strong>Curated warehouse</strong></div></aside><div className="workspace">{page}</div><FloatingRagChatbot /></div>;
}

export default App;
