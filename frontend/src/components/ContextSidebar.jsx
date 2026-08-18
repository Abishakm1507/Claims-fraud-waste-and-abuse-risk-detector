/**
 * Case context and risk factors.
 *
 * WHY EVERY SCORE IS LABELLED
 * Two different scores can exist for one provider:
 *
 *   Provider risk score   from the provider risk model
 *   Overall risk          from multi-agent synthesis, which BLENDS five
 *                         components - and the provider score is one of them,
 *                         weighted 0.30
 *
 * They legitimately differ, and their tier boundaries differ too, so one case
 * can read Critical under one and High under the other. Shown as bare numbers
 * side by side an investigator cannot tell which is which and may act on the
 * wrong one. So the label always names what produced the number, and when a
 * synthesis score is shown its component breakdown appears beneath it - the
 * breakdown is what explains the difference.
 *
 * Renders only when the API supplies a real score. No placeholder state.
 */
function impactOf(factor) {
  const c = factor.contribution;
  if (typeof c !== "number") return "medium";
  if (c >= 0.66) return "high";
  if (c >= 0.33) return "medium";
  return "low";
}

const LABEL = { high: "High impact", medium: "Medium impact", low: "Low impact" };

export default function ContextSidebar({ riskScore, riskFactors, modelInformation }) {
  if (riskScore === null || riskScore === undefined) return null;

  const level = modelInformation?.risk_level;
  const levelKey = String(level || "").toLowerCase();
  const entityId = modelInformation?.entity_id;
  const scoredAt = modelInformation?.scored_at;
  const peerGroup = modelInformation?.peer_group;
  const priority = modelInformation?.priority;
  const scoreLabel = modelInformation?.score_label || "Risk score";
  const components = modelInformation?.component_scores || [];

  return (
    <aside className="sidebar">
      <div className="card">
        <h3>Case context</h3>

        {entityId && (
          <div className="row">
            <span>{modelInformation?.entity_type === "claim" ? "Claim ID" : "Provider ID"}</span>
            <span>{entityId}</span>
          </div>
        )}

        <div className="row">
          <span>Status</span>
          <span><span className="pill flag">Flagged</span></span>
        </div>

        <div className="row">
          <span>{scoreLabel}</span>
          <span>{riskScore} / 100</span>
        </div>

        {level && (
          <div className="row">
            <span>Risk level</span>
            <span><span className={`pill ${levelKey}`}>{level}</span></span>
          </div>
        )}

        {priority && (
          <div className="row">
            <span>Priority</span>
            <span>{priority}</span>
          </div>
        )}

        {peerGroup && (
          <div className="row">
            <span>Peer group</span>
            <span>{peerGroup}</span>
          </div>
        )}

        {scoredAt && (
          <div className="row">
            <span>Period scored</span>
            <span>{scoredAt}</span>
          </div>
        )}
      </div>

      {components.length > 0 && (
        <div className="card">
          <h3>Score components</h3>
          <p className="card-note">
            The overall score blends these. Each is scored separately, so they
            can differ from one another and from the total.
          </p>
          {components.map((c, i) => (
            <div className="row" key={i}>
              <span>
                {c.name}
                {c.is_provider_model && <em className="tag"> provider model</em>}
              </span>
              <span>{c.value}</span>
            </div>
          ))}
        </div>
      )}

      {Array.isArray(riskFactors) && riskFactors.length > 0 && (
        <div className="card">
          <h3>Risk factors</h3>
          {riskFactors.map((f, i) => {
            const impact = impactOf(f);
            return (
              <div className="factor" key={i}>
                <span className={`factor-dot ${impact}`} />
                <span className="factor-name">
                  {f.name}
                  {f.agent && <em className="tag"> {f.agent}</em>}
                </span>
                <span className={`pill ${impact}`}>{LABEL[impact]}</span>
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
}
