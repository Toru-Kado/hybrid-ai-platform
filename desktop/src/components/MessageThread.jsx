/**
 * @file Scrollable message thread with virtualisation for large sessions.
 *
 * Renders the full conversation as a vertically-scrolling log. For sessions
 * exceeding VIRTUALIZATION_THRESHOLD messages, switches to @tanstack/react-virtual
 * for efficient DOM recycling. Handles:
 *   - Auto-scroll to bottom during streaming / loading
 *   - Search-result scroll-into-view for highlighted messages
 *   - Empty-state / loading / error placeholders via ThreadStateCard
 */

import { useCallback, useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import MessageBubble from "./MessageBubble";
import ThreadStateCard from "./ThreadStateCard";

const ESTIMATED_MESSAGE_HEIGHT = 120;
const OVERSCAN = 5;
const VIRTUALIZATION_THRESHOLD = 50;

function VirtualizedMessages({
  messages,
  scrollRef,
  streamingMessageId,
  isLoading,
  latestAssistantPair,
  isBusy,
  searchQuery,
  highlightedMessageId,
  onCopyMessage,
  onCopyCode,
  onRegenerate,
}) {
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ESTIMATED_MESSAGE_HEIGHT,
    overscan: OVERSCAN,
  });

  const scrollToBottom = useCallback(() => {
    if (messages.length > 0) {
      virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
    }
  }, [messages.length, virtualizer]);

  useEffect(() => {
    if (streamingMessageId || isLoading) {
      scrollToBottom();
    }
  }, [streamingMessageId, isLoading, messages.length, scrollToBottom]);

  useEffect(() => {
    if (highlightedMessageId) {
      const index = messages.findIndex((m) => m.message_id === highlightedMessageId);
      if (index >= 0) {
        virtualizer.scrollToIndex(index, { align: "center" });
      }
    }
  }, [highlightedMessageId, messages, virtualizer]);

  return (
    <div
      style={{
        height: `${virtualizer.getTotalSize()}px`,
        width: "100%",
        position: "relative",
      }}
    >
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const message = messages[virtualItem.index];
        return (
          <div
            key={message.message_id}
            data-index={virtualItem.index}
            ref={virtualizer.measureElement}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <MessageBubble
              message={message}
              isStreaming={streamingMessageId === message.message_id}
              isLatestAssistant={latestAssistantPair?.assistantMessage.message_id === message.message_id}
              canRegenerate={!isBusy && latestAssistantPair?.assistantMessage.message_id === message.message_id}
              searchQuery={searchQuery}
              isHighlighted={highlightedMessageId === message.message_id}
              onCopyMessage={() => onCopyMessage(message)}
              onCopyCode={onCopyCode}
              onRegenerate={onRegenerate}
            />
          </div>
        );
      })}
    </div>
  );
}

function PlainMessages({
  messages,
  streamingMessageId,
  latestAssistantPair,
  isBusy,
  searchQuery,
  highlightedMessageId,
  onCopyMessage,
  onCopyCode,
  onRegenerate,
}) {
  return messages.map((message) => (
    <MessageBubble
      key={message.message_id}
      message={message}
      isStreaming={streamingMessageId === message.message_id}
      isLatestAssistant={latestAssistantPair?.assistantMessage.message_id === message.message_id}
      canRegenerate={!isBusy && latestAssistantPair?.assistantMessage.message_id === message.message_id}
      searchQuery={searchQuery}
      isHighlighted={highlightedMessageId === message.message_id}
      onCopyMessage={() => onCopyMessage(message)}
      onCopyCode={onCopyCode}
      onRegenerate={onRegenerate}
    />
  ));
}

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
  searchQuery,
  highlightedMessageId,
  onRetryFromError,
  onCreateSession,
  onCopyMessage,
  onCopyCode,
  onRegenerate,
}) {
  const scrollRef = useRef(null);
  const useVirtual = messages.length >= VIRTUALIZATION_THRESHOLD;

  const showMessages = !isLoadingHistory && errorState?.context !== "history" && messages.length > 0;

  useEffect(() => {
    if (!useVirtual && highlightedMessageId && scrollRef.current) {
      const el = scrollRef.current.querySelector(`.message.search-active`);
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }
  }, [highlightedMessageId, useVirtual]);

  return (
    <div
      className="thread"
      ref={(node) => {
        scrollRef.current = node;
        if (typeof threadRef === "function") {
          threadRef(node);
        } else if (threadRef) {
          threadRef.current = node;
        }
      }}
      role="log"
      aria-label="Conversation messages"
      aria-live="polite"
      aria-relevant="additions"
    >
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
      ) : null}

      {showMessages && useVirtual ? (
        <VirtualizedMessages
          messages={messages}
          scrollRef={scrollRef}
          streamingMessageId={streamingMessageId}
          isLoading={isLoading}
          latestAssistantPair={latestAssistantPair}
          isBusy={isBusy}
          searchQuery={searchQuery}
          highlightedMessageId={highlightedMessageId}
          onCopyMessage={onCopyMessage}
          onCopyCode={onCopyCode}
          onRegenerate={onRegenerate}
        />
      ) : showMessages ? (
        <PlainMessages
          messages={messages}
          streamingMessageId={streamingMessageId}
          latestAssistantPair={latestAssistantPair}
          isBusy={isBusy}
          searchQuery={searchQuery}
          highlightedMessageId={highlightedMessageId}
          onCopyMessage={onCopyMessage}
          onCopyCode={onCopyCode}
          onRegenerate={onRegenerate}
        />
      ) : null}

      {isLoading ? <div className="thinking" role="status" aria-label="Assistant is generating a response">Assistant is thinking...</div> : null}
    </div>
  );
}
