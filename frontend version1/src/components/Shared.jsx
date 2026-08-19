import { useEffect, useRef } from "react";

export const Loading = ({ what = "Loading" }) => (
  <div className="loading"><span className="spin" />{what}…</div>
);

export const ErrorBox = ({ children }) => (
  <div className="errorbox">{children}</div>
);

export const Pill = ({ tier }) => {
  if (!tier) return <span style={{ color: "var(--faint)" }}>—</span>;
  const k = String(tier).toLowerCase();
  return <span className={`pill ${k}`}>{tier}</span>;
};

export const Stat = ({ label, value, sub, tone }) => (
  <div className={`stat${tone === "critical" ? " crit" : ""}`}>
    <div className="lb">{label}</div>
    <div className="vl">{value}</div>
    {sub && <div className="sb">{sub}</div>}
  </div>
);

/**
 * Charts are hand-drawn SVG rather than a library: a handful of small charts
 * do not justify the dependency, and this keeps every colour bound to the same
 * risk-tier tokens the pills and tables use, so a band reads identically
 * wherever it appears.
 */
const TIER_FILL = {
  Critical: "#B5231C", "Very high": "#E05341", High: "#E8891F",
  Medium: "#DFAF1E", Low: "#1FA463",
};
const BLUE = "#4F6FE5", AXIS = "#9AA1AF", GRID = "#EDEFF4";

const fmt = n => (n >= 1000 ? n.toLocaleString() : String(n));
function niceMax(v, ticks) {
  const raw = v / ticks;
  const pow = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * pow).find(s => s >= raw) || 10 * pow;
  return step * ticks;
}

export function HBar({ rows, ticks = 6, width = 560, tiered = false }) {
  if (!rows?.length) return <div className="empty">No data for this chart.</div>;
  const rowH = 44, padL = 96, padR = 16, padT = 8, padB = 30;
  const H = padT + rows.length * rowH + padB;
  const max = niceMax(Math.max(...rows.map(r => r.v)) || 1, ticks);
  const plotW = width - padL - padR;
  return (
    <svg viewBox={`0 0 ${width} ${H}`} width="100%" role="img">
      {Array.from({ length: ticks + 1 }, (_, i) => {
        const x = padL + (plotW * i) / ticks;
        return (
          <g key={i}>
            <line x1={x} y1={padT} x2={x} y2={padT + rows.length * rowH}
                  stroke={GRID} />
            <text x={x} y={H - 10} fill={AXIS} fontSize="10.5"
                  fontFamily="IBM Plex Mono, monospace" textAnchor="middle">
              {fmt(Math.round((max * i) / ticks))}
            </text>
          </g>
        );
      })}
      {rows.map((r, i) => {
        const y = padT + i * rowH + 9, h = rowH - 18;
        const w = Math.max(2, (plotW * r.v) / max);
        return (
          <g key={r.k}>
            <text x={padL - 11} y={y + h / 2 + 4} fill="#3D4359" fontSize="12.5"
                  fontFamily="Inter, sans-serif" textAnchor="end">{r.k}</text>
            <rect x={padL} y={y} width={w} height={h} rx="3"
                  fill={tiered ? TIER_FILL[r.k] || BLUE : BLUE}>
              <title>{`${r.k}: ${fmt(r.v)}`}</title>
            </rect>
          </g>
        );
      })}
    </svg>
  );
}

export function VBar({ rows }) {
  if (!rows?.length) return <div className="empty">No data for this chart.</div>;
  const W = 560, H = 232, padL = 50, padR = 10, padT = 12, padB = 28;
  const max = niceMax(Math.max(...rows.map(r => r.v)) || 1, 4);
  const plotW = W - padL - padR, plotH = H - padT - padB, step = plotW / rows.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
      {Array.from({ length: 5 }, (_, i) => {
        const y = padT + plotH * (1 - i / 4);
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke={GRID} />
            <text x={padL - 9} y={y + 4} fill={AXIS} fontSize="10.5"
                  fontFamily="IBM Plex Mono, monospace" textAnchor="end">
              {fmt(Math.round((max * i) / 4))}
            </text>
          </g>
        );
      })}
      {rows.map((r, i) => {
        const bw = step * 0.42, x = padL + step * i + (step - bw) / 2;
        const h = (plotH * r.v) / max;
        return (
          <g key={r.k}>
            <rect x={x} y={padT + plotH - h} width={bw} height={h} rx="3" fill={BLUE}>
              <title>{`${r.k}: ${fmt(r.v)}`}</title>
            </rect>
            <text x={padL + step * i + step / 2} y={H - 9} fill={AXIS}
                  fontSize="10.5" fontFamily="IBM Plex Mono, monospace"
                  textAnchor="middle">{r.k}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function LineChart({ rows }) {
  if (!rows?.length) return <div className="empty">No data for this chart.</div>;
  const W = 560, H = 232, padL = 52, padR = 12, padT = 12, padB = 28;
  const max = niceMax(Math.max(...rows.map(r => r.v)) || 1, 5);
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const X = i => padL + (plotW * i) / Math.max(1, rows.length - 1);
  const Y = v => padT + plotH * (1 - v / max);
  const pts = rows.map((r, i) => `${X(i)},${Y(r.v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
      {Array.from({ length: 6 }, (_, i) => {
        const y = padT + plotH * (1 - i / 5);
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke={GRID} />
            <text x={padL - 9} y={y + 4} fill={AXIS} fontSize="10.5"
                  fontFamily="IBM Plex Mono, monospace" textAnchor="end">
              {fmt(Math.round((max * i) / 5))}
            </text>
          </g>
        );
      })}
      <polygon points={`${padL},${padT + plotH} ${pts} ${X(rows.length - 1)},${padT + plotH}`}
               fill={BLUE} opacity=".10" />
      <polyline points={pts} fill="none" stroke="#2563EB" strokeWidth="2"
                strokeLinejoin="round" strokeLinecap="round" />
      {rows.map((r, i) => (
        <g key={r.k}>
          <circle cx={X(i)} cy={Y(r.v)} r="3.6" fill="#fff" stroke="#2563EB"
                  strokeWidth="2"><title>{`${r.k}: ${fmt(r.v)}`}</title></circle>
          <text x={X(i)} y={H - 9} fill={AXIS} fontSize="10.5"
                fontFamily="IBM Plex Mono, monospace" textAnchor="middle">{r.k}</text>
        </g>
      ))}
    </svg>
  );
}

/** Debounce a changing value — used so typing in a filter doesn't fire a
 *  request per keystroke. */
export function useDebounced(value, ms = 350) {
  const ref = useRef(value);
  useEffect(() => {
    const t = setTimeout(() => { ref.current = value; }, ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return ref.current;
}
