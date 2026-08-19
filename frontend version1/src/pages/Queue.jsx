import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProviders, getFilters, describeError } from "../lib/api.js";
import { Loading, ErrorBox, Pill } from "../components/Shared.jsx";

const PAGE = 25;

export default function Queue() {
  const [d, setD] = useState(null), [err, setErr] = useState(null);
  const [opts, setOpts] = useState({ specialties: [], states: [], tiers: [] });
  const [tier, setTier] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [state, setState] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [minPay, setMinPay] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => { getFilters().then(setOpts).catch(() => {}); }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      setD(null);
      getProviders({
        limit: PAGE, offset: page * PAGE,
        tier: tier || undefined, specialty: specialty || undefined,
        state: state || undefined, search: search || undefined,
        min_score: minScore || undefined, max_score: maxScore || undefined,
        min_payment: minPay || undefined,
      }).then(setD).catch(e => setErr(describeError(e)));
    }, 350);
    return () => clearTimeout(t);
  }, [page, tier, specialty, state, search, minScore, maxScore, minPay]);

  const clear = () => {
    setTier(""); setSpecialty(""); setState(""); setMinScore("");
    setMaxScore(""); setMinPay(""); setSearch(""); setPage(0);
  };
  const onFilter = fn => v => { setPage(0); fn(v); };

  if (err) return <ErrorBox>{err}</ErrorBox>;

  return (
    <>
      <div className="head">
        <div><h1>Investigator queue</h1>
          <p>{d ? `${d.total.toLocaleString()} providers match the current filters. ` : ""}
            Ranking is a statistical prioritisation for review, not an accusation.</p></div>
        <div className="controls">
          <button className="btn ghost" onClick={clear}>Clear all filters</button>
        </div>
      </div>

      <div className="queue">
        <aside className="filters">
          <div className="fgroup">
            <div className="flabel">Risk tier</div>
            {(opts.tiers.length ? opts.tiers : ["Critical", "High", "Medium", "Low"])
              .map(t => (
                <label className="chk" key={t}>
                  <input type="radio" name="tier" checked={tier === t}
                         onChange={() => onFilter(setTier)(t)} />
                  <Pill tier={t} />
                </label>
              ))}
            {tier && <button className="link" style={{ fontSize: 12, marginTop: 6 }}
                             onClick={() => onFilter(setTier)("")}>Any tier</button>}
          </div>

          <div className="fgroup">
            <div className="flabel">Specialty</div>
            <select value={specialty} onChange={e => onFilter(setSpecialty)(e.target.value)}
                    style={{ width: "100%" }}>
              <option value="">All specialties</option>
              {opts.specialties.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="fgroup">
            <div className="flabel">State</div>
            <select value={state} onChange={e => onFilter(setState)(e.target.value)}
                    style={{ width: "100%" }}>
              <option value="">All states</option>
              {opts.states.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="fgroup">
            <div className="flabel">Risk score range</div>
            <div className="range">
              <input type="number" placeholder="Min" value={minScore}
                     onChange={e => onFilter(setMinScore)(e.target.value)} />
              <input type="number" placeholder="Max" value={maxScore}
                     onChange={e => onFilter(setMaxScore)(e.target.value)} />
            </div>
          </div>

          <div className="fgroup">
            <div className="flabel">Minimum total payment</div>
            <input type="number" placeholder="e.g. 100000" value={minPay}
                   onChange={e => onFilter(setMinPay)(e.target.value)} />
          </div>

          <div className="fgroup">
            <div className="flabel">Search name / NPI</div>
            <input type="text" placeholder="Provider name or NPI" value={search}
                   onChange={e => onFilter(setSearch)(e.target.value)} />
          </div>
        </aside>

        <div className="card" style={{ margin: 0 }}>
          {!d ? <Loading what="Loading queue" /> : !d.rows.length ? (
            <div className="empty">No providers match these filters.</div>
          ) : (
            <>
              <table>
                <thead><tr>
                  <th>Provider</th><th>Specialty</th><th>Location</th><th>Tier</th>
                  <th className="num">Risk ▾</th><th className="num">Total payment</th>
                  <th className="num">Benes</th><th></th>
                </tr></thead>
                <tbody>
                  {d.rows.map(r => (
                    <tr key={r.npi}>
                      <td><div className="pname">{r.name || "—"}</div>
                        <div className="pnpi">NPI {r.npi}</div></td>
                      <td>{r.specialty || "—"}</td>
                      <td>{r.location || "—"}</td>
                      <td><Pill tier={r.risk_tier} /></td>
                      <td className="num">{r.risk_score ?? "—"}</td>
                      <td className="num">{r.total_payment}</td>
                      <td className="num">{r.beneficiaries.toLocaleString()}</td>
                      <td style={{ textAlign: "right" }}>
                        <Link className="link" to={`/quick/${r.npi}`}>Quick view →</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="pager">
                <span>Showing {page * PAGE + 1}–{Math.min((page + 1) * PAGE, d.total)} of {d.total.toLocaleString()}</span>
                <span style={{ display: "flex", gap: 8 }}>
                  <button className="btn ghost" disabled={page === 0}
                          onClick={() => setPage(p => p - 1)}>Previous</button>
                  <button className="btn ghost" disabled={(page + 1) * PAGE >= d.total}
                          onClick={() => setPage(p => p + 1)}>Next</button>
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
