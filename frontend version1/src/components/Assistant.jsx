import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { ask, describeError } from "../lib/api.js";

/**
 * Floating investigation assistant.
 *
 * It carries the case context from whichever page opened it, so a question on
 * an investigation page is asked about that case rather than in the abstract.
 */
export default function Assistant({ context }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); },
            [msgs, busy]);

  // The last entity discussed, so a follow-up ("what should I investigate?")
  // resolves to that case instead of resolving nothing.
  const [lastCase, setLastCase] = useState(null);

  const send = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setMsgs(m => [...m, { role: "user", text: q }]);
    setInput(""); setBusy(true);
    try {
      // Page context wins; otherwise carry whatever the conversation last
      // resolved to.
      const d = await ask(q, context?.id ? context : lastCase);
      if (d.context_entity)
        setLastCase({ id: d.context_entity, kind: d.context_kind || "provider" });
      setMsgs(m => [...m, { role: "bot", text: d.answer, sources: d.sources }]);
    } catch (e) {
      setMsgs(m => [...m, { role: "bot", text: describeError(e), error: true }]);
    } finally { setBusy(false); }
  };

  if (!open)
    return (
      <button className="fab" onClick={() => setOpen(true)}>
        💬 Ask the assistant
      </button>
    );

  return (
    <div className="chat on">
      <div className="chat-head">
        <div><b>Investigation assistant</b>
          <span>{context?.id ? `Case: ${context.kind} ${context.id}`
                             : "General questions"}</span></div>
        <button onClick={() => setOpen(false)} aria-label="Close">×</button>
      </div>
      <div className="chat-body">
        {msgs.length === 0 && (
          <div className="msg a">
            <b>ASSISTANT</b>
            {context?.id
              ? "Ask why this case was flagged, what the numbers mean, or what to examine next."
              : "Ask about a fraud concept, a provider, a claim, or why a case was flagged."}
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div className="msg u" key={i}>{m.text}</div>
          ) : (
            <div className="msg a" key={i}>
              <b>ASSISTANT</b>
              <ReactMarkdown>{m.text}</ReactMarkdown>
              {m.sources?.length > 0 && (
                <div className="ctx">{m.sources.length} knowledge source
                  {m.sources.length > 1 ? "s" : ""} used</div>
              )}
            </div>
          )
        )}
        {busy && <div className="loading"><span className="spin" />Thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="chat-foot">
        <input value={input} onChange={e => setInput(e.target.value)}
               onKeyDown={e => e.key === "Enter" && send()}
               placeholder="Ask about this case or any concept"
               disabled={busy} aria-label="Your question" />
        <button onClick={send} disabled={busy} aria-label="Send">→</button>
      </div>
    </div>
  );
}
