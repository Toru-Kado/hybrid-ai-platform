/**
 * @file Root application component — assembles the full desktop UI.
 *
 * Composes the top-level layout from three custom hooks (useChat,
 * useMessageSearch, useTextPrediction) and presentational components.
 * Responsible for:
 *   - Wiring hook state/actions into the component tree
 *   - Theme initialisation and toggle
 *   - Native menu action forwarding (new session, export, toggle sidebar)
 *   - Cross-session search navigation (loading a session from search results)
 */

import { useEffect, useRef, useState } from "react";
import appIcon from "../assets/icon.png";
import ChatHeader from "./components/ChatHeader";
import ChatInput from "./components/ChatInput";
import CrossSessionResults from "./components/CrossSessionResults";
import ErrorBanner from "./components/ErrorBanner";
import UpdateBanner from "./components/UpdateBanner";
import MessageThread from "./components/MessageThread";
import PreferencesPanel from "./components/PreferencesPanel";
import SearchBar from "./components/SearchBar";
import SessionSidebar from "./components/SessionSidebar";
import useChat from "./hooks/useChat";
import useMessageSearch from "./hooks/useMessageSearch";
import useTextPrediction from "./hooks/useTextPrediction";
import { getStoredTheme, getEffectiveTheme, applyTheme, storeTheme } from "./theme";

export default function App() {
  const chat = useChat();
  const search = useMessageSearch({
    messages: chat.messages,
    activeSession: chat.activeSession,
  });
  const prediction = useTextPrediction({
    prompt: chat.prompt,
    isBusy: chat.isBusy,
  });
  const [theme, setTheme] = useState(() => getEffectiveTheme(getStoredTheme()));

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (search.activeCrossResult) {
      chat.loadSession(search.activeCrossResult.session_id);
    }
  }, [search.activeCrossResult]);

  const chatRef = useRef(chat);
  chatRef.current = chat;

  useEffect(() => {
    if (!window.assistantApi?.onMenuAction) return;
    return window.assistantApi.onMenuAction((action) => {
      const c = chatRef.current;
      switch (action) {
        case "new-session":
          c.createSession();
          break;
        case "export-transcript":
          c.exportActiveSession("markdown");
          break;
        case "toggle-sidebar":
          c.toggleSidebar();
          break;
      }
    });
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    storeTheme(next);
  }

  return (
    <main className="shell">
      <a href="#prompt" className="skip-link">Skip to chat input</a>
      <section className="hero">
        <div>
          <p className="eyebrow">Toru Kado Desktop POC</p>
          <h1>TK-AI</h1>
          <p className="lede">
            A local desktop client for Anthropic Claude through Amazon Bedrock,
            with SQLite-backed session history and markdown-rendered responses.
          </p>
        </div>
        <div className="hero-brandmark">
          <div className="hero-icon-frame">
            <img className="hero-icon" src={appIcon} alt="TK-AI icon" />
          </div>
        </div>
      </section>

      <section
        className={`chat-layout ${chat.isCompactLayout ? "compact" : ""}${!chat.isSidebarOpen && !chat.isCompactLayout ? " sidebar-collapsed" : ""}`}
        style={{ "--sidebar-width": `${chat.sidebarWidth}px` }}
      >
        {chat.isCompactLayout && chat.isSidebarOpen ? (
          <button
            type="button"
            className="sidebar-scrim"
            aria-label="Close session history"
            onClick={() => chat.setIsSidebarOpen(false)}
          />
        ) : null}

        <SessionSidebar
          isCompactLayout={chat.isCompactLayout}
          isSidebarOpen={chat.isSidebarOpen}
          isLoadingSessions={chat.isLoadingSessions}
          sessions={chat.sessions}
          filteredSessions={chat.filteredSessions}
          activeSession={chat.activeSession}
          sessionFilter={chat.sessionFilter}
          isBusy={chat.isBusy}
          onSetSessionFilter={chat.setSessionFilter}
          onCreateSession={chat.createSession}
          onLoadSession={chat.loadSession}
          onCloseSidebar={() => chat.setIsSidebarOpen(false)}
        />

        {!chat.isCompactLayout ? (
          <div
            className="sidebar-resizer"
            role="separator"
            aria-label="Resize session sidebar"
            aria-orientation="vertical"
            onPointerDown={chat.startSidebarResize}
          />
        ) : null}

        <section className="chat-panel">
          <ChatHeader
            health={chat.health}
            isCompactLayout={chat.isCompactLayout}
            isSidebarOpen={chat.isSidebarOpen}
            isControlsOpen={chat.isControlsOpen}
            isRenamingSession={chat.isRenamingSession}
            activeSession={chat.activeSession}
            renameTitle={chat.renameTitle}
            isBusy={chat.isBusy}
            theme={theme}
            onToggleTheme={toggleTheme}
            onToggleSidebar={chat.toggleSidebar}
            onSetIsControlsOpen={chat.setIsControlsOpen}
            onSetIsRenamingSession={chat.setIsRenamingSession}
            onSetRenameTitle={chat.setRenameTitle}
            onSubmitRename={chat.submitRenameSession}
            onDeleteSession={chat.deleteActiveSession}
            onExportSession={chat.exportActiveSession}
          />

          {chat.errorState ? (
            <ErrorBanner
              errorState={chat.errorState}
              onRetry={
                chat.errorState.retry && chat.errorState.context !== "history"
                  ? chat.retryFromError
                  : null
              }
              onDismiss={() => chat.setErrorState(null)}
            />
          ) : null}
          <UpdateBanner />
          {chat.notice ? <div className="notice" role="status" aria-live="polite">{chat.notice}</div> : null}

          <PreferencesPanel
            isControlsOpen={chat.isControlsOpen}
            health={chat.health}
            systemPrompt={chat.systemPrompt}
            temperature={chat.temperature}
            maxTokens={chat.maxTokens}
            isBusy={chat.isBusy}
            predictionEnabled={prediction.isEnabled}
            onSetSystemPrompt={chat.setSystemPrompt}
            onSetTemperature={chat.setTemperature}
            onSetMaxTokens={chat.setMaxTokens}
            onSetPredictionEnabled={prediction.setIsEnabled}
          />

          <SearchBar
            isSearchOpen={search.isSearchOpen}
            searchQuery={search.searchQuery}
            searchMode={search.searchMode}
            localResults={search.localResults}
            crossResults={search.crossResults}
            activeMatchIndex={search.activeMatchIndex}
            isSearching={search.isSearching}
            onSetSearchQuery={search.setSearchQuery}
            onSetSearchMode={search.setSearchMode}
            onNavigateMatch={search.navigateMatch}
            onClose={search.closeSearch}
          />

          {search.isSearchOpen && search.searchMode === "all" ? (
            <CrossSessionResults
              results={search.crossResults}
              activeMatchIndex={search.activeMatchIndex}
              onSelectResult={(result) => {
                search.selectCrossResult(result);
                chat.loadSession(result.session_id);
              }}
            />
          ) : null}

          <MessageThread
            threadRef={chat.threadRef}
            messages={chat.messages}
            isLoadingHistory={chat.isLoadingHistory}
            isLoadingSessions={chat.isLoadingSessions}
            isLoading={chat.isLoading}
            errorState={chat.errorState}
            activeSession={chat.activeSession}
            streamingMessageId={chat.streamingMessageId}
            latestAssistantPair={chat.latestAssistantPair}
            isBusy={chat.isBusy}
            searchQuery={search.isSearchOpen ? search.searchQuery : ""}
            highlightedMessageId={search.highlightedMessageId}
            onRetryFromError={chat.retryFromError}
            onCreateSession={chat.createSession}
            onCopyMessage={chat.copyMessageContent}
            onCopyCode={chat.copyCodeBlock}
            onRegenerate={chat.regenerateLatestReply}
          />

          <ChatInput
            prompt={chat.prompt}
            isLoading={chat.isLoading}
            streamingMessageId={chat.streamingMessageId}
            isBusy={chat.isBusy}
            onSetPrompt={chat.setPrompt}
            onSubmit={chat.submitPrompt}
            suggestion={prediction.suggestion}
            onAcceptFull={prediction.acceptFull}
            onAcceptWord={prediction.acceptWord}
            onDismiss={prediction.dismiss}
          />
        </section>
      </section>
    </main>
  );
}
