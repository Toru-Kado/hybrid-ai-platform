import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import appIcon from "../assets/icon.png";
import {
  DEFAULT_SIDEBAR_WIDTH,
  clampSidebarWidth,
  readCompactViewport,
} from "./layout";

const fallbackApi = {
  health: async () => {
    const response = await fetch("http://127.0.0.1:8765/api/health");
    return response.json();
  },
  listSessions: async () => {
    const response = await fetch("http://127.0.0.1:8765/api/sessions");
    return response.json();
  },
  createSession: async (payload) => {
    const response = await fetch("http://127.0.0.1:8765/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    return response.json();
  },
  getSession: async (sessionId) => {
    const response = await fetch(`http://127.0.0.1:8765/api/sessions/${sessionId}`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to load session.");
    }
    return body;
  },
  renameSession: async (sessionId, payload) => {
    const response = await fetch(`http://127.0.0.1:8765/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to rename session.");
    }
    return body;
  },
  deleteSession: async (sessionId) => {
    const response = await fetch(`http://127.0.0.1:8765/api/sessions/${sessionId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      let body = {};
      try {
        body = await response.json();
      } catch (_error) {
        body = {};
      }
      throw new Error(body.error || "Failed to delete session.");
    }
  },
  chat: async (payload) => {
    const response = await fetch("http://127.0.0.1:8765/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Assistant request failed.");
    }
    return body;
  },
};

function api() {
  return window.assistantApi || fallbackApi;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isRenamingSession, setIsRenamingSession] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [isCompactLayout, setIsCompactLayout] = useState(() => readCompactViewport());
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => !readCompactViewport());
  const [isControlsOpen, setIsControlsOpen] = useState(() => !readCompactViewport());
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const threadRef = useRef(null);
  const resizeCleanupRef = useRef(() => {});
  const previousCompactRef = useRef(readCompactViewport());
  const revealTimerRef = useRef(null);
  const revealRunRef = useRef(0);

  const isBusy = isLoading || streamingMessageId !== null;

  useEffect(() => {
    let isMounted = true;

    async function initialize() {
      try {
        const [healthPayload, sessionsPayload] = await Promise.all([
          api().health(),
          api().listSessions(),
        ]);
        if (!isMounted) {
          return;
        }
        setHealth(healthPayload);
        const nextSessions = sessionsPayload.sessions || [];
        setSessions(nextSessions);
        if (nextSessions.length > 0) {
          await loadSession(nextSessions[0].session_id, { isMounted });
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught.message);
        }
      } finally {
        if (isMounted) {
          setIsLoadingSessions(false);
        }
      }
    }

    initialize();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const container = threadRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [messages, isLoading, streamingMessageId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    function syncLayoutMode() {
      setIsCompactLayout(readCompactViewport());
    }

    window.addEventListener("resize", syncLayoutMode);
    return () => {
      window.removeEventListener("resize", syncLayoutMode);
    };
  }, []);

  useEffect(() => {
    const previousCompact = previousCompactRef.current;
    if (previousCompact === isCompactLayout) {
      return;
    }
    previousCompactRef.current = isCompactLayout;
    setIsSidebarOpen(!isCompactLayout);
    setIsControlsOpen(!isCompactLayout);
  }, [isCompactLayout]);

  useEffect(
    () => () => {
      resizeCleanupRef.current();
      cancelAssistantReveal();
    },
    [],
  );

  useEffect(() => {
    if (isRenamingSession) {
      return;
    }
    setRenameTitle(activeSession?.title || "");
  }, [activeSession, isRenamingSession]);

  async function loadSession(sessionId, options = {}) {
    const { isMounted = true } = options;
    cancelAssistantReveal();
    setIsLoadingHistory(true);
    setError("");
    try {
      const payload = await api().getSession(sessionId);
      if (!isMounted) {
        return;
      }
      setActiveSession(payload.session);
      setMessages(payload.messages || []);
      setIsRenamingSession(false);
    } catch (caught) {
      if (isMounted) {
        setError(caught.message);
      }
    } finally {
      if (isMounted) {
        setIsLoadingHistory(false);
      }
    }
  }

  async function createSession() {
    cancelAssistantReveal();
    setError("");
    try {
      const payload = await api().createSession({});
      const session = payload.session;
      setSessions((current) => [session, ...current]);
      setActiveSession(session);
      setMessages([]);
      setIsRenamingSession(true);
      setRenameTitle(session.title);
      if (isCompactLayout) {
        setIsSidebarOpen(false);
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function submitPrompt(event) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setError("Write a prompt first.");
      return;
    }

    const pendingUserMessage = {
      message_id: `pending-user-${Date.now()}`,
      role: "user",
      content: trimmedPrompt,
      created_at: new Date().toISOString(),
      metadata: null,
    };
    const assistantMessageId = `assistant-${Date.now()}`;

    setIsLoading(true);
    setError("");
    setMessages((current) => [...current, pendingUserMessage]);
    setPrompt("");

    try {
      const payload = await api().chat({
        session_id: activeSession?.session_id,
        prompt: trimmedPrompt,
        system_prompt: systemPrompt || undefined,
        temperature: Number(temperature),
        max_tokens: Number(maxTokens),
      });
      const session = payload.session;
      setActiveSession(session);
      setSessions((current) => mergeSession(current, session));
      const persistedUserMessage = {
        ...pendingUserMessage,
        message_id: `user-${session.session_id}-${Date.now()}`,
      };
      setMessages((current) => [
        ...current.filter((item) => item.message_id !== pendingUserMessage.message_id),
        persistedUserMessage,
        {
          ...payload.message,
          message_id: assistantMessageId,
          content: "",
          metadata: {
            ...(payload.message.metadata || {}),
            is_streaming: true,
          },
        },
      ]);
      startAssistantReveal({
        ...payload.message,
        message_id: assistantMessageId,
      });
    } catch (caught) {
      setMessages((current) =>
        current.filter((item) => item.message_id !== pendingUserMessage.message_id),
      );
      setPrompt(trimmedPrompt);
      setError(caught.message);
    } finally {
      setIsLoading(false);
    }
  }

  function toggleSidebar() {
    setIsSidebarOpen((current) => !current);
  }

  function cancelAssistantReveal() {
    revealRunRef.current += 1;
    if (revealTimerRef.current) {
      window.clearInterval(revealTimerRef.current);
      revealTimerRef.current = null;
    }
    setStreamingMessageId(null);
  }

  function startAssistantReveal(message) {
    cancelAssistantReveal();
    const content = message.content || "";
    if (!content) {
      setMessages((current) =>
        current.map((item) =>
          item.message_id === message.message_id
            ? { ...message, metadata: message.metadata || null }
            : item,
        ),
      );
      return;
    }

    const runId = revealRunRef.current;
    const chunkSize = Math.max(6, Math.ceil(content.length / 30));
    let nextLength = 0;
    setStreamingMessageId(message.message_id);

    function applyChunk() {
      if (runId !== revealRunRef.current) {
        return;
      }
      nextLength = Math.min(content.length, nextLength + chunkSize);
      const isComplete = nextLength >= content.length;
      setMessages((current) =>
        current.map((item) =>
          item.message_id === message.message_id
            ? {
                ...message,
                content: content.slice(0, nextLength),
                metadata: isComplete
                  ? message.metadata || null
                  : {
                      ...(message.metadata || {}),
                      is_streaming: true,
                    },
              }
            : item,
        ),
      );
      if (isComplete) {
        if (revealTimerRef.current) {
          window.clearInterval(revealTimerRef.current);
          revealTimerRef.current = null;
        }
        setStreamingMessageId(null);
      }
    }

    applyChunk();
    if (content.length <= chunkSize) {
      return;
    }
    revealTimerRef.current = window.setInterval(applyChunk, 24);
  }

  async function submitRenameSession(event) {
    event.preventDefault();
    if (!activeSession) {
      return;
    }

    const nextTitle = renameTitle.trim();
    if (!nextTitle) {
      setError("Session title cannot be empty.");
      return;
    }

    setError("");
    try {
      const payload = await api().renameSession(activeSession.session_id, { title: nextTitle });
      setActiveSession(payload.session);
      setSessions((current) => replaceSession(current, payload.session));
      setIsRenamingSession(false);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function deleteActiveSession() {
    if (!activeSession) {
      return;
    }
    if (!window.confirm(`Delete "${activeSession.title}"?`)) {
      return;
    }

    cancelAssistantReveal();
    setError("");
    try {
      await api().deleteSession(activeSession.session_id);
      const remainingSessions = sessions.filter(
        (item) => item.session_id !== activeSession.session_id,
      );
      setSessions(remainingSessions);
      setIsRenamingSession(false);
      if (remainingSessions.length > 0) {
        await loadSession(remainingSessions[0].session_id);
      } else {
        setActiveSession(null);
        setMessages([]);
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  function startSidebarResize(event) {
    if (isCompactLayout) {
      return;
    }

    const startX = event.clientX;
    const startWidth = sidebarWidth;

    function handlePointerMove(moveEvent) {
      const delta = moveEvent.clientX - startX;
      setSidebarWidth(clampSidebarWidth(startWidth + delta));
    }

    function stopResizing() {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResizing);
      resizeCleanupRef.current = () => {};
    }

    resizeCleanupRef.current = stopResizing;
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResizing);
  }

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
        className={`chat-layout ${isCompactLayout ? "compact" : ""}`}
        style={{ "--sidebar-width": `${sidebarWidth}px` }}
      >
        {isCompactLayout && isSidebarOpen ? (
          <button
            type="button"
            className="sidebar-scrim"
            aria-label="Close session history"
            onClick={() => setIsSidebarOpen(false)}
          />
        ) : null}

        <aside
          className={`sidebar ${isCompactLayout ? "compact" : ""} ${
            isSidebarOpen ? "open" : ""
          }`}
          aria-hidden={isCompactLayout && !isSidebarOpen}
          aria-label="Conversation history"
        >
          <div className="sidebar-header">
            <div>
              <p className="sidebar-kicker">Sessions</p>
              <h2>Conversation history</h2>
            </div>
            <button
              type="button"
              className="secondary-button primary-sidebar-button"
              disabled={isBusy}
              onClick={createSession}
            >
              New chat
            </button>
          </div>
          <div className="session-list">
            {isLoadingSessions ? (
              <p className="session-placeholder">Loading saved sessions...</p>
            ) : sessions.length === 0 ? (
              <p className="session-placeholder">No sessions yet. Start a new chat.</p>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.session_id}
                  type="button"
                  className={`session-item ${
                    activeSession?.session_id === session.session_id ? "active" : ""
                  }`}
                  onClick={() => {
                    loadSession(session.session_id);
                    if (isCompactLayout) {
                      setIsSidebarOpen(false);
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

        {!isCompactLayout ? (
          <div
            className="sidebar-resizer"
            role="separator"
            aria-label="Resize session sidebar"
            aria-orientation="vertical"
            onPointerDown={startSidebarResize}
          />
        ) : null}

        <section className="chat-panel">
          <header className="chat-header">
            <div className="chat-heading">
              {isCompactLayout ? (
                <button
                  type="button"
                  className="secondary-button sidebar-toggle"
                  onClick={toggleSidebar}
                >
                  {isSidebarOpen ? "Hide sessions" : "Show sessions"}
                </button>
              ) : null}
              <div className="session-header-stack">
                <p className="sidebar-kicker">Current session</p>
                {isRenamingSession ? (
                  <form className="session-title-form" onSubmit={submitRenameSession}>
                    <input
                      aria-label="Session title"
                      value={renameTitle}
                      onChange={(event) => setRenameTitle(event.target.value)}
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
                          setIsRenamingSession(false);
                          setRenameTitle(activeSession?.title || "");
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
                          onClick={() => setIsRenamingSession(true)}
                        >
                          Rename session
                        </button>
                        <button
                          type="button"
                          className="secondary-button compact-button danger-button"
                          disabled={isBusy}
                          onClick={deleteActiveSession}
                        >
                          Delete session
                        </button>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            </div>
            <StatusStrip health={health} />
          </header>

          {error ? <div className="error">{error}</div> : null}

          <div className="thread" ref={threadRef}>
            {isLoadingHistory ? (
              <div className="thread-placeholder">Loading conversation...</div>
            ) : messages.length === 0 ? (
              <div className="thread-placeholder">
                Start a session and the full conversation will scroll here.
              </div>
            ) : (
              messages.map((message) => (
                <MessageBubble
                  key={message.message_id}
                  message={message}
                  isStreaming={streamingMessageId === message.message_id}
                />
              ))
            )}
            {isLoading ? <div className="thinking">Assistant is thinking...</div> : null}
          </div>

          <form className="composer" onSubmit={submitPrompt}>
            <div className="composer-topline">
              <label htmlFor="prompt">Prompt</label>
              <button
                type="button"
                className="secondary-button composer-toggle"
                aria-expanded={isControlsOpen}
                disabled={isBusy}
                onClick={() => setIsControlsOpen((current) => !current)}
              >
                {isControlsOpen ? "Hide controls" : "Show controls"}
              </button>
            </div>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              disabled={isBusy}
              placeholder="Ask the platform assistant..."
            />

            <div className="composer-grid" hidden={!isControlsOpen}>
              <label>
                System prompt override
                <input
                  value={systemPrompt}
                  disabled={isBusy}
                  onChange={(event) => setSystemPrompt(event.target.value)}
                  placeholder="Optional"
                />
              </label>
              <label>
                Temperature
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  disabled={isBusy}
                  onChange={(event) => setTemperature(event.target.value)}
                />
              </label>
              <label>
                Max tokens
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={maxTokens}
                  disabled={isBusy}
                  onChange={(event) => setMaxTokens(event.target.value)}
                />
              </label>
            </div>

            <button type="submit" disabled={isBusy}>
              {isLoading ? "Thinking..." : streamingMessageId ? "Streaming..." : "Send message"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function StatusStrip({ health }) {
  return (
    <div className="status-strip">
      <span className="status-pill">{health ? "Connected" : "Starting"}</span>
      <span>{health?.provider || "bedrock"}</span>
      <span>{health?.aws_region || "us-east-1"}</span>
      <span>{health?.target_kind || "inference profile"}</span>
    </div>
  );
}

function MessageBubble({ message, isStreaming = false }) {
  const isAssistant = message.role === "assistant";
  const metadata = message.metadata || {};

  return (
    <article className={`message ${isAssistant ? "assistant" : "user"}`}>
      <header>
        <strong>{isAssistant ? "Assistant" : "You"}</strong>
        <span>{formatTimestamp(message.created_at)}</span>
      </header>

      {isAssistant ? (
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      ) : (
        <p className="plain-message">{message.content}</p>
      )}

      {isStreaming ? <footer className="streaming-indicator">Streaming response...</footer> : null}

      {isAssistant && metadata.request_id ? (
        <footer>
          <span>{metadata.output_tokens ?? "?"} output tokens</span>
          <span>{metadata.latency_ms ?? "?"} ms</span>
        </footer>
      ) : null}
    </article>
  );
}

function mergeSession(current, session) {
  const existing = current.filter((item) => item.session_id !== session.session_id);
  return [session, ...existing];
}

function replaceSession(current, session) {
  return current.map((item) => (item.session_id === session.session_id ? session : item));
}

function formatTimestamp(value) {
  try {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch (_error) {
    return "";
  }
}
