/** Opening screen. Deliberately plain - no prompts, no suggestions. */
export default function EmptyState() {
  return (
    <div className="empty">
      <h2>How can I help with this investigation?</h2>
      <p>
        Ask about fraud concepts, claims terminology, a specific provider or
        claim, or why a case was flagged.
      </p>
    </div>
  );
}
