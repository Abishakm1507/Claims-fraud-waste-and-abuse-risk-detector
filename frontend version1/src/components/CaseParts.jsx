import { Pill, Stat } from "./Shared.jsx";

/**
 * The score band.
 *
 * Every score carries the label of what produced it. Two scores can exist for
 * one provider — the provider risk model's own, and the multi-agent synthesis
 * that blends it with four other components — and they legitimately differ.
 * Shown as bare numbers they would be mistaken for one another, so the
 * component breakdown sits directly beside the headline and shows why.
 */
export function RiskBand({ risk }) {
  if (!risk || risk.score == null)
    return (
      <div className="riskband" style={{ gridTemplateColumns: "1fr" }}>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 13.5 }}>
          {risk?.message || "No model output available for this case."}
        </p>
      </div>
    );

  const comps = risk.components || [];
  const max = Math.max(100, ...comps.filter(c => !c.not_run)
                                    .map(c => parseFloat(c.value) || 0));
  return (
    <div className="riskband">
      <div className="bigscore">
        <div className="n">{risk.score}</div>
        <div className="d">/ 100</div>
        <div className="lb">{risk.level || "Risk"}</div>
        <div className="src">{risk.score_label || "risk score"}</div>
      </div>
      <div className="comps">
        {comps.length === 0 && (
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--muted)" }}>
            No component breakdown reported for this case.
          </p>
        )}
        {comps.map((c, i) => {
          // A component whose agent never ran is shown as "not run", not as a
          // bar at zero — zero reads as checked-and-clean.
          if (c.not_run) {
            return (
              <div className="comp" key={i} title={c.reason || ""}>
                <div className="cn" style={{ color: "var(--faint)" }}>
                  {c.name}<em>not applicable</em>
                </div>
                <div className="bar" style={{ opacity: 0.45 }} />
                <div className="cv" style={{ color: "var(--faint)" }}>—</div>
              </div>
            );
          }
          const v = parseFloat(c.value) || 0;
          const pct = Math.min(100, (v / max) * 100);
          return (
            <div className="comp" key={i}>
              <div className="cn">{c.name}
                {c.is_provider_model && <em>provider model</em>}</div>
              <div className="bar"><i className={pct >= 90 ? "hot" : ""}
                                     style={{ width: `${pct}%` }} /></div>
              <div className="cv">{c.value}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Agent cards. A skipped agent gets a card, never an omission — an absent
 *  card would read as "nothing found here". */
export function AgentCards({ agents }) {
  if (!agents?.length) return null;
  return (
    <div className="agents">
      {agents.map((a, i) =>
        a.status === "skipped" ? (
          <div className="agent skipped" key={i}>
            <div className="agent-top">
              <div><h3>{a.name}</h3><div className="role">{a.role}</div></div>
              <span className="pill skip">Not run</span>
            </div>
            <p className="skipreason">{a.reason}</p>
          </div>
        ) : (
          <div className="agent" key={i}>
            <div className="agent-top">
              <div><h3>{a.name}</h3><div className="role">{a.role}</div></div>
              <span className="pill ok">{a.findings.length} finding
                {a.findings.length === 1 ? "" : "s"}</span>
            </div>
            {a.findings.map((f, j) => (
              <div className="finding" key={j}>
                <b>{f.title}</b>
                {f.detail && <p>{f.detail}</p>}
                {f.evidence?.length > 0 && (
                  <div className="ev">
                    {f.evidence.map((e, k) => <span key={k}>{e}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

export function PeerTable({ rows }) {
  if (!rows?.length) return null;
  return (
    <div className="card">
      <h2>Peer comparison</h2>
      <p className="sub">
        Ratio measures magnitude; percentile measures rarity. A high percentile
        with a small ratio means the peer distribution is tight, not that the
        provider is far from normal.
      </p>
      <table>
        <thead><tr>
          <th>Metric</th><th className="num">This provider</th>
          <th className="num">Peer median</th><th className="num">Ratio</th>
          <th className="num">Percentile</th>
        </tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.metric}</td>
              <td className="num">{r.provider ?? "—"}</td>
              <td className="num">{r.peer_median ?? "—"}</td>
              <td className="num" style={{ fontWeight: 600 }}>{r.ratio ?? "—"}</td>
              <td className="num">{r.percentile ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MetricRow({ metrics }) {
  if (!metrics?.length) return null;
  return (
    <div className="stats">
      {metrics.map((m, i) => (
        <Stat key={i} label={m.label} value={m.value} />
      ))}
    </div>
  );
}

/** What was not examined. Rendered even when empty, because an investigator
 *  needs to know the difference between "checked and clean" and "not checked". */
export function Gaps({ gaps, agents }) {
  const skipped = (agents || []).filter(a => a.status === "skipped");
  if (!gaps?.length && !skipped.length) return null;
  return (
    <div className="gap">
      <h2>Not examined</h2>
      <p>An absent finding here is not a clean result.</p>
      <ul>
        {skipped.map((a, i) => <li key={`s${i}`}><b>{a.name}</b> — {a.reason}</li>)}
        {(gaps || []).map((g, i) => <li key={`g${i}`}>{g}</li>)}
      </ul>
    </div>
  );
}

export function TopProcedures({ rows }) {
  if (!rows?.length) return null;
  const cols = ["code", "description", "services", "payment", "vs state average"];
  const present = cols.filter(c => rows.some(r => r[c] != null));
  return (
    <div className="card">
      <h2>Highest-value procedures</h2>
      <p className="sub">Where this provider's payment is concentrated</p>
      <table>
        <thead><tr>{present.map(c =>
          <th key={c} className={c === "code" || c === "description" ? "" : "num"}>
            {c.charAt(0).toUpperCase() + c.slice(1)}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{present.map(c => (
              <td key={c} className={c === "code" ? "mono"
                        : c === "description" ? "" : "num"}>{r[c] ?? "—"}</td>
            ))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
