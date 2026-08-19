import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getClaims, describeError } from "../lib/api.js";
import { Loading, ErrorBox } from "../components/Shared.jsx";

const PAGE = 25;

export default function Claims() {
  const [d, setD] = useState(null), [err, setErr] = useState(null);
  const [page, setPage] = useState(0), [type, setType] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      setD(null);
      getClaims({ limit: PAGE, offset: page * PAGE,
                  claim_type: type || undefined, search: search || undefined })
        .then(setD).catch(e => setErr(describeError(e)));
    }, search ? 350 : 0);
    return () => clearTimeout(t);
  }, [page, type, search]);

  if (err) return <ErrorBox>{err}</ErrorBox>;

  return (
    <>
      <div className="head">
        <div><h1>Claims</h1><p>Claim-level detail across outpatient, inpatient and carrier</p></div>
        <div className="controls">
          <select value={type} onChange={e => { setPage(0); setType(e.target.value); }}>
            <option value="">All claim types</option>
            <option value="outpatient">Outpatient</option>
            <option value="inpatient">Inpatient</option>
            <option value="carrier">Carrier</option>
          </select>
          <input type="text" placeholder="Search claim or provider ID"
                 value={search} style={{ width: 230 }}
                 onChange={e => { setPage(0); setSearch(e.target.value); }} />
        </div>
      </div>

      <div className="card">
        {!d ? <Loading what="Loading claims" /> : !d.rows.length ? (
          <div className="empty">No claims match those filters.</div>
        ) : (
          <>
            <div className="tbl-head">
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                {d.total.toLocaleString()} claims
              </span>
            </div>
            <table>
              <thead><tr>
                <th>Claim ID</th><th>Type</th><th>Provider</th><th>Service date</th>
                <th className="num">Payment</th><th className="num">Charge</th><th></th>
              </tr></thead>
              <tbody>
                {d.rows.map(r => (
                  <tr key={r.claim_id}>
                    <td className="mono">{r.claim_id}</td>
                    <td>{r.claim_type}</td>
                    <td className="mono">{r.provider || "—"}
                      <span style={{ color: "var(--faint)", fontSize: 11 }}> {r.provider_kind}</span>
                    </td>
                    <td>{r.service_date || "—"}</td>
                    <td className="num">{r.payment}</td>
                    <td className="num">{r.charge}</td>
                    <td style={{ textAlign: "right" }}>
                      <Link className="link" to={`/investigate/claim/${encodeURIComponent(r.claim_id)}`}>
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
