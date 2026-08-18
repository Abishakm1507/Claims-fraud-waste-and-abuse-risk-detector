import ReactMarkdown from "react-markdown";

/**
 * Renders the assistant's answer.
 *
 * LLM output is Markdown, so it is rendered rather than shown raw. Headings are
 * colour-coded by what they say, so an investigator can scan an answer for the
 * part they need: reasons, meaning, legitimate explanations, next steps.
 */
function headingClass(children) {
  const text = String(children).toLowerCase();
  if (text.includes("legitimate") || text.includes("explanation")) return "h-legit";
  if (text.includes("mean") || text.includes("indicate")) return "h-means";
  if (text.includes("investigate") || text.includes("next") || text.includes("examine"))
    return "h-next";
  if (text.includes("data") || text.includes("appears")) return "h-data";
  return "";
}

const components = {
  h1: ({ children }) => <h3 className={headingClass(children)}>{children}</h3>,
  h2: ({ children }) => <h3 className={headingClass(children)}>{children}</h3>,
  h3: ({ children }) => <h3 className={headingClass(children)}>{children}</h3>,
  h4: ({ children }) => <h3 className={headingClass(children)}>{children}</h3>,
};

export default function Answer({ text, isError }) {
  if (isError) return <div className="answer error">{text}</div>;

  return (
    <div className="answer">
      <ReactMarkdown components={components}>{text}</ReactMarkdown>
    </div>
  );
}
