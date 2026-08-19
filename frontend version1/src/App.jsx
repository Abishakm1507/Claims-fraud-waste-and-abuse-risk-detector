import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import Assistant from "./components/Assistant.jsx";
import Overview from "./pages/Overview.jsx";
import Providers from "./pages/Providers.jsx";
import Claims from "./pages/Claims.jsx";
import Queue from "./pages/Queue.jsx";
import Investigation from "./pages/Investigation.jsx";
import { getOverview, getProviders, getClaims } from "./lib/api.js";

export default function App() {
  const [counts, setCounts] = useState({});
  // Case context flows from whichever investigation page is open, so the
  // assistant answers about that case rather than in the abstract.
  const [context, setContext] = useState(null);

  useEffect(() => {
    getOverview().catch(() => {});
    Promise.all([
      getProviders({ limit: 1 }).catch(() => ({ total: undefined })),
      getClaims({ limit: 1 }).catch(() => ({ total: undefined })),
    ]).then(([p, c]) =>
      setCounts({ providers: p.total, claims: c.total, queue: p.total }));
  }, []);

  return (
    <div className="app">
      <Sidebar counts={counts} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/providers" element={<Providers />} />
          <Route path="/claims" element={<Claims />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/quick/:id"
                 element={<Investigation kind="provider" quick onContext={setContext} />} />
          <Route path="/investigate/provider/:id"
                 element={<Investigation kind="provider" onContext={setContext} />} />
          <Route path="/investigate/claim/:id"
                 element={<Investigation kind="claim" onContext={setContext} />} />
        </Routes>
      </main>
      <Assistant context={context} />
    </div>
  );
}
