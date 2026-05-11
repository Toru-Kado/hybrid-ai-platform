import { useEffect, useRef } from "react";

export default function CrossSessionResults({
  results,
  activeMatchIndex,
  onSelectResult,
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const active = containerRef.current.querySelector("[aria-selected='true']");
    if (active) {
      active.scrollIntoView({ block: "nearest" });
    }
  }, [activeMatchIndex]);

  if (!results || results.length === 0) return null;

  return (
    <div ref={containerRef} className="cross-session-results" role="listbox" aria-label="Search results across sessions">
      {results.map((result, index) => (
        <button
          key={`${result.session_id}-${result.message_id}`}
          type="button"
          className={`cross-session-result ${index === activeMatchIndex ? "active" : ""}`}
          aria-selected={index === activeMatchIndex}
          role="option"
          onClick={() => onSelectResult(result)}
        >
          <span className="cross-result-session">{result.session_title}</span>
          <span className="cross-result-role">{result.role}</span>
          <span
            className="cross-result-snippet"
            dangerouslySetInnerHTML={{ __html: result.snippet }}
          />
        </button>
      ))}
    </div>
  );
}
