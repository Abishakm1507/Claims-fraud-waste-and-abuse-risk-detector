import { useState } from "react";
import RagChatbot from "./RagChatbot.jsx";

export default function FloatingRagChatbot() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        className="rag-launcher"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Close RAG chatbot" : "Open RAG chatbot"}
      >
        {open ? "Close" : "Chat"}
      </button>
      {open && (
        <aside className="rag-float-panel">
          <button
            className="rag-close"
            onClick={() => setOpen(false)}
            aria-label="Close RAG chatbot"
          >
            Close
          </button>
          <RagChatbot />
        </aside>
      )}
    </>
  );
}
