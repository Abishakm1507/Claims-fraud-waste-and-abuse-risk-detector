import { useEffect, useState } from "react";
import { getOverview, describeError } from "../lib/api.js";
import { Loading, ErrorBox, Stat, HBar, VBar, LineChart } from "../components/Shared.jsx";

export default function Overview() {
  const [d, setD] = useState(null), [err, setErr] = useState(null);
  useEffect(() => { getOverview().then(setD).catch(e => setErr(describeError(e))); }, []);

  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!d) return <Loading what="Loading overview" />;
  if (!d.available) return <ErrorBox>{d.message}</ErrorBox>;

  const c = d.charts || {};
  return (
    <>
      <div className="head">
        <div><h1>Overview</h1>
          <p>Claims and Medicare provider data, read from the curated tables.</p></div>
      </div>

      {/* The caveat is part of the reading, not a footnote: the two datasets
          use different identifier systems and cannot be cross-joined. */}
      <div className="note"><span>⚠</span><div>
        Claims and provider data come from different time windows and identifier
        systems (claim <code>PROVIDER_ID</code> vs CMS <code>NPI</code>) — figures
        below are shown side by side, not cross-joined.
      </div></div>

      <div className="stats">
        {d.cards.map(card => <Stat key={card.label} {...card} />)}
      </div>

      <div className="grid2">
        <div className="card"><h2>Claims volume by year</h2>
          <p className="sub">Claims with a recorded service date</p>
          <LineChart rows={c.claims_by_year} /></div>
        <div className="card"><h2>Rendering providers by year</h2>
          <p className="sub">Distinct NPIs billing Medicare Part B</p>
          <VBar rows={c.providers_by_year} /></div>
      </div>

      {/* Side by side deliberately: claim bands are quintile cuts and provider
          bands are model output. Without the subtitles saying so, a flat claim
          chart reads as a finding rather than an artefact of the banding. */}
      <div className="grid2">
        <div className="card"><h2>Claim risk distribution</h2>
          <p className="sub">Quantile-based bands — near-equal by construction,
            not model output</p>
          <HBar rows={c.claim_risk_distribution} ticks={5} tiered /></div>
        <div className="card"><h2>Provider risk distribution</h2>
          <p className="sub">Isolation forest ensemble score, scored providers only</p>
          <HBar rows={c.provider_risk_distribution} ticks={4} tiered /></div>
      </div>

      <div className="card"><h2>Claims by type</h2>
        <p className="sub">Outpatient, inpatient, carrier</p>
        <HBar rows={c.claims_by_type} ticks={6} width={1180} /></div>
    </>
  );
}
