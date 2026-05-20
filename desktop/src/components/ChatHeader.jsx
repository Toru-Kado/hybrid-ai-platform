/**
 * @file Chat panel header — session title, actions, runtime badge, and theme toggle.
 *
 * Displays the current session name with inline rename editing, session
 * management buttons (delete, export), the sidebar toggle for compact layouts,
 * a runtime connection summary, theme switcher, and preferences panel toggle.
 */

import RuntimeSummary from "./RuntimeSummary";

export default function ChatHeader({
  health,
  isCompactLayout,
  isSidebarOpen,
  isControlsOpen,
  isRenamingSession,
  activeSession,
  renameTitle,
  isBusy,
  theme,
  onToggleTheme,
  onToggleSidebar,
  onSetIsControlsOpen,
  onSetIsRenamingSession,
  onSetRenameTitle,
  onSubmitRename,
  onDeleteSession,
  onExportSession,
}) {
  return (
    <header className="chat-header">
      <div className="chat-heading">
        {isCompactLayout || !isSidebarOpen ? (
          <button
            type="button"
            className="secondary-button sidebar-toggle"
            onClick={onToggleSidebar}
          >
            {isSidebarOpen ? "Hide sessions" : "Show sessions"}
          </button>
        ) : null}
        <div className="session-header-stack">
          <p className="sidebar-kicker">Current session</p>
          {isRenamingSession ? (
            <form className="session-title-form" onSubmit={onSubmitRename}>
              <input
                aria-label="Session title"
                value={renameTitle}
                onChange={(event) => onSetRenameTitle(event.target.value)}
              />
              <div className="session-action-row">
                <button type="submit" className="secondary-button compact-button">
                  Save
                </button>
                <button
                  type="button"
                  className="secondary-button compact-button subtle-button"
                  disabled={isBusy}
                  onClick={() => {
                    onSetIsRenamingSession(false);
                    onSetRenameTitle(activeSession?.title || "");
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <>
              <h2>{activeSession?.title || "New chat"}</h2>
              {activeSession ? (
                <div className="session-action-row">
                  <button
                    type="button"
                    className="secondary-button compact-button subtle-button"
                    disabled={isBusy}
                    onClick={() => onSetIsRenamingSession(true)}
                  >
                    Rename session
                  </button>
                  <button
                    type="button"
                    className="secondary-button compact-button danger-button"
                    disabled={isBusy}
                    onClick={onDeleteSession}
                  >
                    Delete session
                  </button>
                  <button
                    type="button"
                    className="secondary-button compact-button subtle-button"
                    disabled={isBusy}
                    onClick={() => onExportSession("markdown")}
                  >
                    Export .md
                  </button>
                  <button
                    type="button"
                    className="secondary-button compact-button subtle-button"
                    disabled={isBusy}
                    onClick={() => onExportSession("json")}
                  >
                    Export .json
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
      <div className="chat-header-actions">
        <RuntimeSummary health={health} />
        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button
          type="button"
          className="secondary-button compact-button preferences-toggle"
          aria-expanded={isControlsOpen}
          aria-controls="preferences-panel"
          disabled={isBusy}
          onClick={() => onSetIsControlsOpen((current) => !current)}
        >
          {isControlsOpen ? "Hide preferences" : "Show preferences"}
        </button>
      </div>
    </header>
  );
}
