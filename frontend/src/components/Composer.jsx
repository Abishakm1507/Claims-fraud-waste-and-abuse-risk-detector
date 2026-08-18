import { useRef, useEffect } from "react";

/** Question input. Enter sends; Shift+Enter adds a line. */
export default function Composer({ value, onChange, onSend, disabled }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  };

  return (
    <div className="composer">
      <div className="composer-row">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about fraud, claims, providers, or investigations"
          disabled={disabled}
          aria-label="Your question"
        />
        <button
          className="send"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send"
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M2 8h11M8.5 3.5L13 8l-4.5 4.5" stroke="currentColor"
                  strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
