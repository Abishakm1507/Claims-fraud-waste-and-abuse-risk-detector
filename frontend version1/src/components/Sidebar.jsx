import { NavLink } from "react-router-dom";

export default function Sidebar({ counts }) {
  const item = (to, label, count) => (
    <NavLink to={to} end className={({ isActive }) => `nav${isActive ? " on" : ""}`}>
      {label}
      {count != null && <span className="ct">{count.toLocaleString()}</span>}
    </NavLink>
  );
  return (
    <aside className="side">
      <div className="brand">
        <div className="mk">M</div>
        <div><b>Meridian</b><span>Claims intelligence</span></div>
      </div>
      {item("/", "Overview")}
      <div className="navlabel">Claims</div>
      {item("/claims", "Claims table", counts?.claims)}
      <div className="navlabel">Providers</div>
      {item("/providers", "Providers table", counts?.providers)}
      <div className="navlabel">Investigation</div>
      {item("/queue", "Investigator queue", counts?.queue)}
      <div className="side-foot">
        Risk scores prioritise review.<br />They do not establish fraud.
      </div>
    </aside>
  );
}
