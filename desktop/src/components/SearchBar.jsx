/**
 * @file Search toolbar — inline search within the current session or across all sessions.
 *
 * Appears in-place above the message thread when activated (Cmd/Ctrl+F).
 * Provides a text input, session/all toggle, match counter, and prev/next
 * navigation buttons. Keyboard: Enter = next, Shift+Enter = prev, Escape = close.
 */

export default function SearchBar({
  isSearchOpen,
  searchQuery,
  searchMode,
  localResults,
  crossResults,
  activeMatchIndex,
  isSearching,
  onSetSearchQuery,
  onSetSearchMode,
  onNavigateMatch,
  onClose,
}) {
  if (!isSearchOpen) return null;

  const results = searchMode === "session" ? localResults : crossResults;
  const total = results.length;
  const current = total > 0 ? activeMatchIndex + 1 : 0;

  return (
    <div className="search-bar" role="search" aria-label="Search messages">
      <input
        type="search"
        className="search-bar-input"
        autoFocus
        placeholder={
          searchMode === "session"
            ? "Search this session..."
            : "Search all sessions..."
        }
        value={searchQuery}
        onChange={(e) => onSetSearchQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onNavigateMatch(e.shiftKey ? -1 : 1);
          }
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          }
        }}
        aria-label="Search query"
      />
      <div className="search-bar-controls">
        <label className="search-mode-toggle">
          <input
            type="checkbox"
            checked={searchMode === "all"}
            onChange={(e) => onSetSearchMode(e.target.checked ? "all" : "session")}
          />
          All sessions
        </label>
        <span className="search-bar-count" aria-live="polite">
          {isSearching
            ? "Searching..."
            : total > 0
              ? `${current} of ${total}`
              : searchQuery.trim()
                ? "No matches"
                : ""}
        </span>
        <button
          type="button"
          className="secondary-button compact-button"
          onClick={() => onNavigateMatch(-1)}
          disabled={total === 0}
          aria-label="Previous match"
        >
          Prev
        </button>
        <button
          type="button"
          className="secondary-button compact-button"
          onClick={() => onNavigateMatch(1)}
          disabled={total === 0}
          aria-label="Next match"
        >
          Next
        </button>
        <button
          type="button"
          className="secondary-button compact-button subtle-button"
          onClick={onClose}
          aria-label="Close search"
        >
          Close
        </button>
      </div>
    </div>
  );
}
