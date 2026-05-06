import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import appIcon from "../assets/icon.png";
import {
  buildTranscriptContent,
  buildTranscriptFilename,
  transcriptFormatConfig,
} from "./transcript";
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
  saveTranscript: async (payload) => {
    const config = transcriptFormatConfig(payload?.format);
    const blob = new Blob([payload?.content || ""], { type: config.mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = payload?.suggestedName || `session-transcript.${config.extension}`;
    link.click();
    URL.revokeObjectURL(url);
    return { canceled: false, path: link.download };
  },
  streamChat: async (payload, handlers) => {
    return streamChatOverHttp("http://127.0.0.1:8765/api/chat/stream", payload, handlers);
  },
};

function api() {
  return window.assistantApi || fallbackApi;
}

function streamChatApi() {
  if (window.assistantApi?.streamChat) {
    return window.assistantApi.streamChat;
  }
  return fallbackApi.streamChat;
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
  const [errorState, setErrorState] = useState(null);
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isRenamingSession, setIsRenamingSession] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [isCompactLayout, setIsCompactLayout] = useState(() => readCompactViewport());
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => !readCompactViewport());
  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const threadRef = useRef(null);
  const nextThreadScrollRef = useRef("top");
  const resizeCleanupRef = useRef(() => {});
  const previousCompactRef = useRef(readCompactViewport());
  const mountedRef = useRef(true);
  const latestAssistantPair = findLatestAssistantPair(messages);

  const isBusy = isLoading || streamingMessageId !== null;
  const normalizedSessionFilter = sessionFilter.trim().toLowerCase();
  const filteredSessions = sessions.filter((session) => {
    if (!normalizedSessionFilter) {
      return true;
    }
    const haystack = `${session.title || ""} ${session.preview || ""}`.toLowerCase();
    return haystack.includes(normalizedSessionFilter);
  });

  useEffect(() => {
    mountedRef.current = true;
    initializeApp();
    return () => {
      mountedRef.current = false;
      resizeCleanupRef.current();
    };
  }, []);

  useEffect(() => {
    const container = threadRef.current;
    if (!container) {
      return;
    }
    if (nextThreadScrollRef.current === "top") {
      container.scrollTop = 0;
      nextThreadScrollRef.current = null;
      return;
    }
    if (nextThreadScrollRef.current === "bottom" || isLoading || streamingMessageId !== null) {
      container.scrollTop = container.scrollHeight;
      if (nextThreadScrollRef.current === "bottom") {
        nextThreadScrollRef.current = null;
      }
    }
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
    if (isCompactLayout) {
      setIsControlsOpen(false);
    }
  }, [isCompactLayout]);

  useEffect(() => {
    if (isRenamingSession) {
      return;
    }
    setRenameTitle(activeSession?.title || "");
  }, [activeSession, isRenamingSession]);

  async function initializeApp(options = {}) {
    const { preferredSessionId = null } = options;
    setIsLoadingSessions(true);
    clearFeedback();

    try {
      const [healthPayload, sessionsPayload] = await Promise.all([
        api().health(),
        api().listSessions(),
      ]);
      if (!mountedRef.current) {
        return;
      }
      setHealth(healthPayload);
      const nextSessions = sessionsPayload.sessions || [];
      setSessions(nextSessions);

      if (nextSessions.length === 0) {
        setActiveSession(null);
        setMessages([]);
        return;
      }

      const selectedSessionId =
        preferredSessionId &&
        nextSessions.some((session) => session.session_id === preferredSessionId)
          ? preferredSessionId
          : nextSessions[0].session_id;
      await loadSession(selectedSessionId);
    } catch (caught) {
      if (!mountedRef.current) {
        return;
      }
      setHealth(null);
      setSessions([]);
      setActiveSession(null);
      setMessages([]);
      setErrorState(
        buildErrorState(caught?.message, {
          context: "bootstrap",
          retry: { action: "initialize", label: "Retry connection" },
        }),
      );
    } finally {
      if (mountedRef.current) {
        setIsLoadingSessions(false);
      }
    }
  }

  async function loadSession(sessionId) {
    setStreamingMessageId(null);
    setIsLoadingHistory(true);
    clearFeedback();
    try {
      const payload = await api().getSession(sessionId);
      if (!mountedRef.current) {
        return;
      }
      nextThreadScrollRef.current = "top";
      setActiveSession(payload.session);
      setMessages(payload.messages || []);
      setIsRenamingSession(false);
    } catch (caught) {
      if (mountedRef.current) {
        setErrorState(
          buildErrorState(caught?.message, {
            context: "history",
            retry: { action: "session", label: "Retry loading session", sessionId },
          }),
        );
      }
    } finally {
      if (mountedRef.current) {
        setIsLoadingHistory(false);
      }
    }
  }

  async function createSession() {
    setStreamingMessageId(null);
    clearFeedback();
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
      setErrorState(buildErrorState(caught?.message, { context: "session_create" }));
    }
  }

  async function submitPrompt(event) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setErrorState(
        buildErrorState("Write a prompt first.", {
          context: "prompt",
        }),
      );
      return;
    }

    await sendPrompt({
      session_id: activeSession?.session_id,
      prompt: trimmedPrompt,
      system_prompt: systemPrompt || undefined,
      temperature: Number(temperature),
      max_tokens: Number(maxTokens),
    });
  }

  async function sendPrompt(requestPayload) {
    const trimmedPrompt = requestPayload.prompt.trim();

    const pendingUserMessage = {
      message_id: `pending-user-${Date.now()}`,
      role: "user",
      content: trimmedPrompt,
      created_at: new Date().toISOString(),
      metadata: null,
    };
    const assistantMessageId = `assistant-${Date.now()}`;
    const pendingAssistantMessage = {
      message_id: assistantMessageId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      metadata: { is_streaming: true },
    };
    let persistedUserMessage = null;
    let streamedSession = null;
    let sawDelta = false;

    setIsLoading(true);
    clearFeedback();
    nextThreadScrollRef.current = "bottom";
    setStreamingMessageId(assistantMessageId);
    setMessages((current) => [...current, pendingUserMessage, pendingAssistantMessage]);
    setPrompt("");

    try {
      await streamChatApi()(requestPayload, {
          onSession: async (session) => {
            streamedSession = session;
            setActiveSession(session);
            setSessions((current) => mergeSession(current, session));
          },
          onUserMessage: async (message) => {
            persistedUserMessage = message;
            setMessages((current) =>
              current.map((item) =>
                item.message_id === pendingUserMessage.message_id ? message : item,
              ),
            );
          },
          onTextDelta: async (text) => {
            if (!sawDelta) {
              sawDelta = true;
              setIsLoading(false);
            }
            setMessages((current) =>
              current.map((item) =>
                item.message_id === assistantMessageId
                  ? {
                      ...item,
                      content: `${item.content || ""}${text}`,
                      metadata: {
                        ...(item.metadata || {}),
                        is_streaming: true,
                      },
                    }
                  : item,
              ),
            );
          },
          onComplete: async (payload) => {
            const session = payload.session;
            setActiveSession(session);
            setSessions((current) => mergeSession(current, session));
            setMessages((current) =>
              current.map((item) =>
                item.message_id === assistantMessageId
                  ? {
                      ...payload.message,
                      content: payload.message.content || item.content,
                    }
                  : item,
              ),
            );
          },
        });
    } catch (caught) {
      setMessages((current) =>
        current.filter((item) => {
          if (item.message_id === assistantMessageId) {
            return false;
          }
          if (!persistedUserMessage && item.message_id === pendingUserMessage.message_id) {
            return false;
          }
          return true;
        }),
      );
      if (!persistedUserMessage || !streamedSession) {
        setPrompt(trimmedPrompt);
      }
      setErrorState(
        buildErrorState(caught?.message, {
          context: "prompt",
          retry:
            !persistedUserMessage && !streamedSession
              ? { action: "prompt", label: "Retry request", payload: requestPayload }
              : { action: "restore_prompt", label: "Use prompt again", prompt: trimmedPrompt },
        }),
      );
    } finally {
      setIsLoading(false);
      setStreamingMessageId(null);
    }
  }

  function toggleSidebar() {
    setIsSidebarOpen((current) => !current);
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

    clearFeedback();
    try {
      const payload = await api().renameSession(activeSession.session_id, { title: nextTitle });
      setActiveSession(payload.session);
      setSessions((current) => replaceSession(current, payload.session));
      setIsRenamingSession(false);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "session_rename" }));
    }
  }

  async function deleteActiveSession() {
    if (!activeSession) {
      return;
    }
    if (!window.confirm(`Delete "${activeSession.title}"?`)) {
      return;
    }

    setStreamingMessageId(null);
    clearFeedback();
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
      setErrorState(buildErrorState(caught?.message, { context: "session_delete" }));
    }
  }

  async function exportActiveSession(format) {
    if (!activeSession) {
      return;
    }

    clearFeedback();
    try {
      const result = await api().saveTranscript({
        format,
        suggestedName: buildTranscriptFilename(activeSession, format),
        content: buildTranscriptContent(activeSession, messages, format),
      });
      if (!result?.canceled) {
        setNotice(`Exported ${format === "json" ? "JSON" : "Markdown"} transcript.`);
      }
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "export" }));
    }
  }

  async function copyMessageContent(message) {
    try {
      await writeToClipboard(message.content || "");
      setNotice(message.role === "assistant" ? "Copied assistant message." : "Copied prompt.");
      setErrorState(null);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "clipboard" }));
    }
  }

  async function copyCodeBlock(code) {
    try {
      await writeToClipboard(code);
      setNotice("Copied code block.");
      setErrorState(null);
    } catch (caught) {
      setErrorState(buildErrorState(caught?.message, { context: "clipboard" }));
    }
  }

  async function regenerateLatestReply() {
    if (!latestAssistantPair || isBusy) {
      return;
    }

    const { userMessage } = latestAssistantPair;
    const userMetadata = userMessage.metadata || {};

    setNotice("Regenerating the latest reply from the last prompt.");
    await sendPrompt({
      session_id: activeSession?.session_id,
      prompt: userMessage.content,
      system_prompt:
        typeof userMetadata.system_prompt === "string" && userMetadata.system_prompt.trim()
          ? userMetadata.system_prompt
          : systemPrompt || undefined,
      temperature: Number(temperature),
      max_tokens: Number(maxTokens),
    });
  }

  function clearFeedback() {
    setErrorState(null);
    setNotice("");
  }

  async function retryFromError() {
    const retry = errorState?.retry;
    if (!retry) {
      return;
    }

    if (retry.action === "initialize") {
      await initializeApp();
      return;
    }

    if (retry.action === "session" && retry.sessionId) {
      await loadSession(retry.sessionId);
      return;
    }

    if (retry.action === "prompt" && retry.payload) {
      await sendPrompt(retry.payload);
      return;
    }

    if (retry.action === "restore_prompt" && retry.prompt) {
      setPrompt(retry.prompt);
      setErrorState(null);
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
            <div className="sidebar-title-block">
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
          <div className="sidebar-filter">
            <label htmlFor="session-filter">Search sessions</label>
            <input
              id="session-filter"
              type="search"
              value={sessionFilter}
              onChange={(event) => setSessionFilter(event.target.value)}
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
                        <button
                          type="button"
                          className="secondary-button compact-button subtle-button"
                          disabled={isBusy}
                          onClick={() => exportActiveSession("markdown")}
                        >
                          Export .md
                        </button>
                        <button
                          type="button"
                          className="secondary-button compact-button subtle-button"
                          disabled={isBusy}
                          onClick={() => exportActiveSession("json")}
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
                className="secondary-button compact-button preferences-toggle"
                aria-expanded={isControlsOpen}
                aria-controls="preferences-panel"
                disabled={isBusy}
                onClick={() => setIsControlsOpen((current) => !current)}
              >
                {isControlsOpen ? "Hide preferences" : "Show preferences"}
              </button>
            </div>
          </header>

          {errorState ? (
            <ErrorBanner
              errorState={errorState}
              onRetry={
                errorState.retry && errorState.context !== "history" ? retryFromError : null
              }
              onDismiss={() => setErrorState(null)}
            />
          ) : null}
          {notice ? <div className="notice">{notice}</div> : null}

          <section
            id="preferences-panel"
            className="preferences-panel"
            hidden={!isControlsOpen}
            aria-label="Preferences and runtime"
          >
            <div className="preferences-card runtime-card">
              <div className="preferences-card-head">
                <p className="sidebar-kicker">Runtime</p>
                <span className="runtime-badge">{health ? "Live target" : "Starting"}</span>
              </div>
              <dl className="runtime-grid">
                <div>
                  <dt>Provider</dt>
                  <dd>{formatRuntimeValue(health?.provider, "bedrock")}</dd>
                </div>
                <div>
                  <dt>Region</dt>
                  <dd>{formatRuntimeValue(health?.aws_region, "us-east-1")}</dd>
                </div>
                <div>
                  <dt>Target kind</dt>
                  <dd>{formatTargetKind(health?.target_kind)}</dd>
                </div>
                <div className="runtime-grid-span">
                  <dt>Target</dt>
                  <dd className="runtime-code" title={health?.target_id || "Target unavailable"}>
                    {formatRuntimeValue(health?.target_id, "Pending runtime target")}
                  </dd>
                </div>
                <div className="runtime-grid-span">
                  <dt>Config source</dt>
                  <dd className="runtime-code" title={health?.target_source || "Source unavailable"}>
                    {formatTargetSource(health?.target_source)}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="preferences-card controls-card">
              <div className="preferences-card-head">
                <p className="sidebar-kicker">Preferences</p>
                <span className="runtime-badge muted-badge">Per-session controls</span>
              </div>
              <div className="preferences-grid">
                <label className="panel-field panel-field-wide">
                  System prompt override
                  <input
                    value={systemPrompt}
                    disabled={isBusy}
                    onChange={(event) => setSystemPrompt(event.target.value)}
                    placeholder="Optional"
                  />
                </label>
                <label className="panel-field">
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
                <label className="panel-field">
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
            </div>
          </section>

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
                onAction={errorState.retry ? retryFromError : null}
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
                onAction={!activeSession && !isLoadingSessions ? createSession : null}
              />
            ) : (
              messages.map((message) => (
                <MessageBubble
                  key={message.message_id}
                  message={message}
                  isStreaming={streamingMessageId === message.message_id}
                  isLatestAssistant={latestAssistantPair?.assistantMessage.message_id === message.message_id}
                  canRegenerate={!isBusy && latestAssistantPair?.assistantMessage.message_id === message.message_id}
                  onCopyMessage={() => copyMessageContent(message)}
                  onCopyCode={copyCodeBlock}
                  onRegenerate={regenerateLatestReply}
                />
              ))
            )}
            {isLoading ? <div className="thinking">Assistant is thinking...</div> : null}
          </div>

          <form className="composer" onSubmit={submitPrompt}>
            <div className="composer-topline">
              <label htmlFor="prompt">Prompt</label>
              <p className="composer-note">
                Runtime settings live in the compact preferences panel.
              </p>
            </div>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (!isBusy && prompt.trim()) {
                    submitPrompt(event);
                  }
                }
              }}
              disabled={isBusy}
              placeholder="Ask the platform assistant..."
            />

            <button type="submit" disabled={isBusy}>
              {isLoading ? "Thinking..." : streamingMessageId ? "Streaming..." : "Send message"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function RuntimeSummary({ health }) {
  return (
    <div className="runtime-summary">
      <span className="status-pill">{health ? "Connected" : "Starting"}</span>
      <div className="runtime-summary-copy">
        <strong>{formatTargetKind(health?.target_kind)}</strong>
        <span>
          {formatRuntimeValue(health?.provider, "bedrock")} via{" "}
          {formatRuntimeValue(health?.aws_region, "us-east-1")}
        </span>
      </div>
    </div>
  );
}

function ErrorBanner({ errorState, onRetry, onDismiss }) {
  return (
    <section className={`status-banner status-banner-${errorState.category}`}>
      <div className="status-banner-copy">
        <strong>{errorState.title}</strong>
        <p>{errorState.message}</p>
        {errorState.hint ? <span>{errorState.hint}</span> : null}
      </div>
      <div className="status-banner-actions">
        {onRetry ? (
          <button type="button" className="secondary-button compact-button" onClick={onRetry}>
            {errorState.retry.label}
          </button>
        ) : null}
        <button
          type="button"
          className="secondary-button compact-button subtle-button"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </section>
  );
}

function ThreadStateCard({ title, body, tone = "neutral", actionLabel = null, onAction = null }) {
  return (
    <section className={`thread-state thread-state-${tone}`}>
      <strong>{title}</strong>
      <p>{body}</p>
      {actionLabel && onAction ? (
        <button type="button" className="secondary-button compact-button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}

function MessageBubble({
  message,
  isStreaming = false,
  isLatestAssistant = false,
  canRegenerate = false,
  onCopyMessage,
  onCopyCode,
  onRegenerate,
}) {
  const isAssistant = message.role === "assistant";
  const metadata = message.metadata || {};

  return (
    <article className={`message ${isAssistant ? "assistant" : "user"}`}>
      <header>
        <div className="message-heading">
          <strong>{isAssistant ? "Assistant" : "You"}</strong>
          <span>{formatTimestamp(message.created_at)}</span>
        </div>
        <div className="message-actions">
          <button
            type="button"
            className="secondary-button compact-button subtle-button"
            onClick={onCopyMessage}
          >
            Copy
          </button>
          {isAssistant && isLatestAssistant ? (
            <button
              type="button"
              className="secondary-button compact-button subtle-button"
              onClick={onRegenerate}
              disabled={!canRegenerate}
            >
              Regenerate
            </button>
          ) : null}
        </div>
      </header>

      {isAssistant ? (
        <div className="markdown-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              pre(props) {
                const child = props.children;
                const rawCode =
                  child && typeof child === "object" && "props" in child
                    ? child.props?.children
                    : "";
                const codeText = Array.isArray(rawCode) ? rawCode.join("") : rawCode || "";

                return (
                  <div className="code-block">
                    <div className="code-block-toolbar">
                      <span>Code</span>
                      <button
                        type="button"
                        className="secondary-button compact-button subtle-button"
                        onClick={() => onCopyCode(codeText)}
                      >
                        Copy code
                      </button>
                    </div>
                    <pre>{props.children}</pre>
                  </div>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
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

function formatRuntimeValue(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function buildErrorState(message, options = {}) {
  const context = options.context || "general";
  const normalizedMessage =
    typeof message === "string" && message.trim()
      ? message.trim()
      : "Unexpected desktop application error.";
  const category = classifyErrorCategory(normalizedMessage);

  return {
    context,
    category,
    title: errorTitleFor(category, context),
    message: normalizedMessage,
    hint: errorHintFor(category, context),
    retry: options.retry || null,
  };
}

function classifyErrorCategory(message) {
  if (
    /accessdenied|unauthoriz|expiredtoken|security token|credentials|credential|aws auth|aws sso|sso login|assume role|not authorized/i.test(
      message,
    )
  ) {
    return "auth";
  }
  if (
    /network|timed out|timeout|could not reach|failed to fetch|econn|connection refused|connection reset|offline|did not start within/i.test(
      message,
    )
  ) {
    return "network";
  }
  if (/bedrock|anthropic|provider|throttl|quota|guardrail|validation|model/i.test(message)) {
    return "provider";
  }
  return "general";
}

function errorTitleFor(category, context) {
  if (context === "history" && category !== "auth") {
    return "Could not load this session";
  }
  if (category === "auth") {
    return "AWS authentication needed";
  }
  if (category === "network") {
    return context === "bootstrap" ? "Connection problem" : "Network problem";
  }
  if (category === "provider") {
    return context === "prompt" ? "Provider request failed" : "Provider unavailable";
  }
  if (context === "bootstrap") {
    return "Desktop startup failed";
  }
  return "Something went wrong";
}

function errorHintFor(category, context) {
  if (category === "auth") {
    return "Refresh the active AWS session, then retry. If you use SSO, run aws sso login for the selected profile.";
  }
  if (category === "network") {
    return context === "bootstrap"
      ? "The local assistant API may still be starting, or the desktop app could not reach it."
      : "Check the local API connection and retry once the runtime is reachable again.";
  }
  if (category === "provider") {
    return "The request reached the configured provider path, but the model runtime could not complete it.";
  }
  return null;
}

function formatTargetKind(value) {
  return humanizeRuntimeToken(formatRuntimeValue(value, "inference_profile"));
}

function formatTargetSource(value) {
  return formatRuntimeValue(value, "Runtime target pending");
}

function humanizeRuntimeToken(value) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

async function writeToClipboard(value) {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const success = document.execCommand("copy");
  document.body.removeChild(textarea);

  if (!success) {
    throw new Error("Clipboard access is unavailable in this environment.");
  }
}

function findLatestAssistantPair(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const assistantMessage = messages[index];
    if (assistantMessage?.role !== "assistant") {
      continue;
    }
    for (let candidate = index - 1; candidate >= 0; candidate -= 1) {
      const userMessage = messages[candidate];
      if (userMessage?.role === "user") {
        return { assistantMessage, userMessage };
      }
    }
    break;
  }
  return null;
}

async function streamChatOverHttp(url, payload, handlers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.error || "Assistant request failed.");
  }

  if (!response.body) {
    throw new Error("Streaming is not available in this environment.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const event = parseSseChunk(chunk);
      if (!event) {
        continue;
      }
      if (event.type === "session" && event.payload?.session) {
        await handlers.onSession?.(event.payload.session);
        continue;
      }
      if (event.type === "user_message" && event.payload?.message) {
        await handlers.onUserMessage?.(event.payload.message);
        continue;
      }
      if (event.type === "delta" && typeof event.payload?.text === "string") {
        await handlers.onTextDelta?.(event.payload.text);
        continue;
      }
      if (event.type === "complete" && event.payload) {
        await handlers.onComplete?.(event.payload);
        return event.payload;
      }
      if (event.type === "error") {
        throw new Error(event.payload?.error || "Assistant request failed.");
      }
    }

    if (done) {
      break;
    }
  }

  throw new Error("Assistant stream ended unexpectedly.");
}

function parseSseChunk(chunk) {
  const lines = chunk.split("\n");
  let type = "message";
  const dataLines = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line) {
      continue;
    }
    if (line.startsWith("event:")) {
      type = line.slice("event:".length).trim() || "message";
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    type,
    payload: JSON.parse(dataLines.join("\n")),
  };
}
