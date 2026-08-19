import { useEffect, useRef, useState } from "react";
import { askQuestion, describeError } from "../api/client.js";
import Message from "./Message.jsx";
import Composer from "./Composer.jsx";
import EmptyState from "./EmptyState.jsx";
import ContextSidebar from "./ContextSidebar.jsx";
import "../rag-chatbot.css";

const clock = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function RagChatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;

    setMessages((m) => [...m, { role: "user", text: question, time: clock() }]);
    setInput("");
    setLoading(true);

    try {
      const data = await askQuestion(question);
      setMessages((m) => [...m, { role: "assistant", ...data, time: clock() }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          isError: true,
          answer: describeError(err),
          time: clock(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const latestCase = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.risk_score !== null &&
                 m.risk_score !== undefined);

  return (
    <div className="rag-window">
      <div className="app">
        <header className="topbar">Investigation Assistant</header>

        <div className="body">
          <main className="chat-col">
            <div className="transcript">
              {messages.length === 0 && !loading && <EmptyState />}

              {messages.map((m, i) => (
                <Message key={i} message={m} />
              ))}

              {loading && (
                <div className="thinking">
                  <div className="avatar bot" aria-hidden="true">IA</div>
                  <div className="dots" role="status" aria-label="Thinking">
                    <i /><i /><i />
                  </div>
                </div>
              )}

              <div ref={endRef} />
            </div>

            <Composer
              value={input}
              onChange={setInput}
              onSend={() => send()}
              disabled={loading}
            />
          </main>

          {latestCase && (
            <ContextSidebar
              riskScore={latestCase.risk_score}
              riskFactors={latestCase.risk_factors}
              modelInformation={latestCase.model_information}
            />
          )}
        </div>
      </div>
    </div>
  );
}