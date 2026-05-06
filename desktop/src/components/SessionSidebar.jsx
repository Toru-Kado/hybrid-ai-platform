export default function SessionSidebar({
  isCompactLayout,
  isSidebarOpen,
  isLoadingSessions,
  sessions,
  filteredSessions,
  activeSession,
  sessionFilter,
  isBusy,
  onSetSessionFilter,
  onCreateSession,
  onLoadSession,
  onCloseSidebar,
}) {
  return (
    <aside
      className={`sidebar ${isCompactLayout ? "compact" : ""} ${
        isSidebarOpen ? "open" : ""
      }`}
      aria-hidden={isCompactLayout && !isSidebarOpen}
      aria-label="Conversation history"
    >
      <div className="sidebar-header">
        <div className="sidebar-title-block">
          <p className="sidebar-kicker">Sessions</p>
          <h2>Conversation history</h2>
        </div>
        <button
          type="button"
          className="secondary-button primary-sidebar-button"
          disabled={isBusy}
          onClick={onCreateSession}
        >
          New chat
        </button>
      </div>
      <div className="sidebar-filter">
        <label htmlFor="session-filter">Search sessions</label>
        <input
          id="session-filter"
          type="search"
          value={sessionFilter}
          onChange={(event) => onSetSessionFilter(event.target.value)}
          placeholder="Filter by title or preview..."
        />
      </div>
      <div className="session-list">
        {isLoadingSessions ? (
          <p className="session-placeholder">Loading saved sessions...</p>
        ) : sessions.length === 0 ? (
          <p className="session-placeholder">No sessions yet. Start a new chat.</p>
        ) : filteredSessions.length === 0 ? (
          <p className="session-placeholder">No sessions match this filter.</p>
        ) : (
          filteredSessions.map((session) => (
            <button
              key={session.session_id}
              type="button"
              className={`session-item ${
                activeSession?.session_id === session.session_id ? "active" : ""
              }`}
              onClick={() => {
                onLoadSession(session.session_id);
                if (isCompactLayout) {
                  onCloseSidebar();
                }
              }}
            >
              <strong>{session.title}</strong>
              <span>{session.preview || "No messages yet."}</span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
