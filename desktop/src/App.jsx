import appIcon from "../assets/icon.png";
import ChatHeader from "./components/ChatHeader";
import ChatInput from "./components/ChatInput";
import ErrorBanner from "./components/ErrorBanner";
import MessageThread from "./components/MessageThread";
import PreferencesPanel from "./components/PreferencesPanel";
import SessionSidebar from "./components/SessionSidebar";
import useChat from "./hooks/useChat";

export default function App() {
  const chat = useChat();

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Toru Kado Desktop POC</p>
          <h1>Hybrid AI Platform</h1>
          <p className="lede">
            A local desktop client for Anthropic Claude through Amazon Bedrock,
            with SQLite-backed session history and markdown-rendered responses.
          </p>
        </div>
        <div className="hero-brandmark">
          <div className="hero-icon-frame">
            <img className="hero-icon" src={appIcon} alt="Hybrid AI Platform icon" />
          </div>
        </div>
      </section>

      <section
        className={`chat-layout ${chat.isCompactLayout ? "compact" : ""}`}
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
          {chat.notice ? <div className="notice">{chat.notice}</div> : null}

          <PreferencesPanel
            isControlsOpen={chat.isControlsOpen}
            health={chat.health}
            systemPrompt={chat.systemPrompt}
            temperature={chat.temperature}
            maxTokens={chat.maxTokens}
            isBusy={chat.isBusy}
            onSetSystemPrompt={chat.setSystemPrompt}
            onSetTemperature={chat.setTemperature}
            onSetMaxTokens={chat.setMaxTokens}
          />

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
          />
        </section>
      </section>
    </main>
  );
}
