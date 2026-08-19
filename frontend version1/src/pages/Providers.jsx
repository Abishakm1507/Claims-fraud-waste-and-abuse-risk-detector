import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProviders, describeError } from "../lib/api.js";
import { Loading, ErrorBox, Pill } from "../components/Shared.jsx";

const PAGE = 25;

export default function Providers() {
  const [d, setD] = useState(null), [err, setErr] = useState(null);
  const [page, setPage] = useState(0), [search, setSearch] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      setD(null);
      getProviders({ limit: PAGE, offset: page * PAGE, search: search || undefined })
        .then(setD).catch(e => setErr(describeError(e)));
    }, search ? 350 : 0);
    return () => clearTimeout(t);
  }, [page, search]);

  if (err) return <ErrorBox>{err}</ErrorBox>;

  return (
    <>
      <div className="head">
        <div><h1>Providers</h1><p>Every provider in the curated data, ranked by risk score</p></div>
        <div className="controls">
          <input type="text" placeholder="Search NPI, name, specialty"
                 value={search} style={{ width: 240 }}
                 onChange={e => { setPage(0); setSearch(e.target.value); }} />
        </div>
      </div>

      <div className="card">
        {!d ? <Loading what="Loading providers" /> : !d.rows.length ? (
          <div className="empty">No providers match that search.</div>
        ) : (
          <>
            <div className="tbl-head">
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                {d.total.toLocaleString()} providers
              </span>
            </div>
            <table>
              <thead><tr>
                <th>NPI</th><th>Name</th><th>Specialty</th><th>State</th>
                <th className="num">Risk score</th><th>Risk level</th>
                <th className="num">Total payment</th><th></th>
              </tr></thead>
              <tbody>
                {d.rows.map(r => (
                  <tr key={r.npi}>
                    <td className="mono">{r.npi}</td>
                    <td>{r.name || "—"}</td>
                    <td>{r.specialty || "—"}</td>
                    <td>{r.state || "—"}</td>
                    <td className="num">{r.risk_score ?? "—"}</td>
                    <td><Pill tier={r.risk_tier} /></td>
                    <td className="num">{r.total_payment}</td>
                    <td style={{ textAlign: "right" }}>
                      <Link className="link" to={`/investigate/provider/${r.npi}`}>
                        Investigate →
                      </Link>
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
    </>
  );
}
