import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { getProviderCase, getClaimCase, getReportPdf, downloadBlob, describeError }
  from "../lib/api.js";
import { Loading, ErrorBox } from "../components/Shared.jsx";
import { RiskBand, AgentCards, PeerTable, MetricRow, Gaps, TopProcedures }
  from "../components/CaseParts.jsx";

/**
 * Full investigation, reached from the providers or claims table.
 *
 * `quick` renders the triage variant reached from the queue: the same numbers,
 * without the narrative, ending in a link to this full view. Triage first,
 * escalate on commitment.
 */
export default function Investigation({ kind, quick = false, onContext }) {
  const params = useParams();
  const id = params.id;
  const [c, setC] = useState(null), [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setC(null); setErr(null);
    onContext?.({ kind, id });
    const fetch = kind === "provider" ? getProviderCase : getClaimCase;
    fetch(id, !quick).then(setC).catch(e => setErr(describeError(e)));
    return () => onContext?.(null);
  }, [id, kind, quick]);

  const download = async () => {
    setBusy(true);
    try {
      const blob = await getReportPdf(kind, id);
      const safe = String(id).replace(/[^a-zA-Z0-9-_]/g, "").replace(/^-+/, "");
      downloadBlob(`case-${kind}-${safe}.pdf`, blob);
    } catch (e) { setErr(describeError(e)); }
    finally { setBusy(false); }
  };

  const backTo = quick ? "/queue" : kind === "provider" ? "/providers" : "/claims";
  const backLabel = quick ? "Back to investigator queue"
                          : kind === "provider" ? "Back to providers" : "Back to claims";

  if (err) return <><Link className="link back" to={backTo}>← {backLabel}</Link>
                    <ErrorBox>{err}</ErrorBox></>;
  if (!c) return <><Link className="link back" to={backTo}>← {backLabel}</Link>
                   <Loading what={`Investigating ${kind} ${id}`} /></>;

  if (!c.found)
    return <><Link className="link back" to={backTo}>← {backLabel}</Link>
             <ErrorBox>{c.message}</ErrorBox></>;

  const ident = c.identity || {};
  const title = ident.name || ident["provider name"]
    || `${kind === "claim" ? "Claim" : "Provider"} ${id}`;
  const metaBits = [
    kind === "provider" ? `NPI ${id}` : `Claim ${id}`,
    ident.specialty, ident.location, ident["claim type"],
    ident["billing NPI"] && `billing NPI ${ident["billing NPI"]}`,
    ident["provider CCN"] && `CCN ${ident["provider CCN"]}`,
  ].filter(Boolean);

  return (
    <>
      <Link className="link back" to={backTo}>← {backLabel}</Link>

      <div className="hero">
        <div className="hero-top">
          <div>
            <h1>{title}</h1>
            <p className="meta">{metaBits.join(" · ")}</p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="btn ghost" onClick={download} disabled={busy}>
              {busy ? "Preparing…" : "Download report (PDF)"}
            </button>
            {quick && (
              <Link className="btn" to={`/investigate/${kind}/${encodeURIComponent(id)}`}
                    style={{ textDecoration: "none" }}>
                Open full investigation →
              </Link>
            )}
          </div>
        </div>
        <RiskBand risk={c.risk} />
      </div>

      <MetricRow metrics={c.metrics} />
      <PeerTable rows={c.peer_comparison} />

      {/* Quick view stops here: numbers only, no narrative. */}
      {!quick && (
        <>
          <AgentCards agents={c.agents} />

          {c.explanation?.text && (
            <div className="explain">
              <h2>What this means</h2>
              <div className="by">
                {c.explanation.generated
                  ? "GENERATED FROM CASE EVIDENCE + KNOWLEDGE BASE"
                  : "ASSEMBLED FROM CASE EVIDENCE"}
              </div>
              <ReactMarkdown>{c.explanation.text}</ReactMarkdown>
              {c.explanation.sources?.length > 0 && (
                <div className="sourcelist">
                  Domain knowledge: {c.explanation.sources
                    .slice(0, 4).map(s => s.title).join(" · ")}
                </div>
              )}
            </div>
          )}

          <TopProcedures rows={c.top_procedures} />
        </>
      )}

      <Gaps gaps={c.gaps} agents={c.agents} />

      <div className="card">
        <p className="disclaimer" style={{ borderTop: "none", paddingTop: 0, margin: 0 }}>
          This case does not establish that fraud occurred. The detection model
          was trained without fraud ground-truth labels and identifies
          statistical anomalies. Deviation from peers can reflect case-mix,
          subspecialty practice, or an imperfect peer group. Findings require
          verification against documentation.
        </p>
      </div>
    </>
  );
}
