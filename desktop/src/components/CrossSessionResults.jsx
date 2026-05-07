export default function CrossSessionResults({
  results,
  activeMatchIndex,
  onSelectResult,
}) {
  if (!results || results.length === 0) return null;

  return (
    <div className="cross-session-results" role="listbox" aria-label="Search results across sessions">
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
