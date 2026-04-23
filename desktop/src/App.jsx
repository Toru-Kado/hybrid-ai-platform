import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  const threadRef = useRef(null);

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
  }, [messages, isLoading]);

  async function loadSession(sessionId, options = {}) {
    const { isMounted = true } = options;
    setIsLoadingHistory(true);
    setError("");
    try {
      const payload = await api().getSession(sessionId);
      if (!isMounted) {
        return;
      }
      setActiveSession(payload.session);
      setMessages(payload.messages || []);
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
    setError("");
    try {
      const payload = await api().createSession({});
      const session = payload.session;
      setSessions((current) => [session, ...current]);
      setActiveSession(session);
      setMessages([]);
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
      setMessages((current) => [
        ...current.filter((item) => item.message_id !== pendingUserMessage.message_id),
        {
          ...pendingUserMessage,
          message_id: `user-${session.session_id}-${Date.now()}`,
        },
        payload.message,
      ]);
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
      </section>

      <section className="chat-layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <div>
              <p className="sidebar-kicker">Sessions</p>
              <h2>Conversation history</h2>
            </div>
            <button type="button" className="secondary-button" onClick={createSession}>
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
                  onClick={() => loadSession(session.session_id)}
                >
                  <strong>{session.title}</strong>
                  <span>{session.preview || "No messages yet."}</span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="chat-panel">
          <header className="chat-header">
            <div>
              <p className="sidebar-kicker">Current session</p>
              <h2>{activeSession?.title || "New chat"}</h2>
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
              messages.map((message) => <MessageBubble key={message.message_id} message={message} />)
            )}
            {isLoading ? <div className="thinking">Assistant is thinking...</div> : null}
          </div>

          <form className="composer" onSubmit={submitPrompt}>
            <label htmlFor="prompt">Prompt</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ask the platform assistant..."
            />

            <div className="composer-grid">
              <label>
                System prompt override
                <input
                  value={systemPrompt}
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
                  onChange={(event) => setMaxTokens(event.target.value)}
                />
              </label>
            </div>

            <button type="submit" disabled={isLoading}>
              {isLoading ? "Thinking..." : "Send message"}
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

function MessageBubble({ message }) {
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
