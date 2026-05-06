import MessageBubble from "./MessageBubble";
import ThreadStateCard from "./ThreadStateCard";

export default function MessageThread({
  threadRef,
  messages,
  isLoadingHistory,
  isLoadingSessions,
  isLoading,
  errorState,
  activeSession,
  streamingMessageId,
  latestAssistantPair,
  isBusy,
  onRetryFromError,
  onCreateSession,
  onCopyMessage,
  onCopyCode,
  onRegenerate,
}) {
  return (
    <div className="thread" ref={threadRef}>
      {isLoadingHistory ? (
        <ThreadStateCard
          title="Loading conversation"
          body="Pulling the saved messages for this session from the local store."
          tone="neutral"
        />
      ) : errorState?.context === "history" ? (
        <ThreadStateCard
          title="Conversation unavailable"
          body="The session list is loaded, but this conversation could not be opened right now."
          tone="warning"
          actionLabel={errorState.retry?.label}
          onAction={errorState.retry ? onRetryFromError : null}
        />
      ) : messages.length === 0 ? (
        <ThreadStateCard
          title={activeSession ? "This session is empty" : "Start a new chat"}
          body={
            activeSession
              ? "Send the first prompt and the full conversation will build here."
              : isLoadingSessions
                ? "Connecting to the desktop runtime and local session store."
                : "Create a session to begin a new conversation."
          }
          tone="neutral"
          actionLabel={!activeSession && !isLoadingSessions ? "New chat" : null}
          onAction={!activeSession && !isLoadingSessions ? onCreateSession : null}
        />
      ) : (
        messages.map((message) => (
          <MessageBubble
            key={message.message_id}
            message={message}
            isStreaming={streamingMessageId === message.message_id}
            isLatestAssistant={latestAssistantPair?.assistantMessage.message_id === message.message_id}
            canRegenerate={!isBusy && latestAssistantPair?.assistantMessage.message_id === message.message_id}
            onCopyMessage={() => onCopyMessage(message)}
            onCopyCode={onCopyCode}
            onRegenerate={onRegenerate}
          />
        ))
      )}
      {isLoading ? <div className="thinking">Assistant is thinking...</div> : null}
    </div>
  );
}
