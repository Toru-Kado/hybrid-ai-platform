import { useEffect, useState } from "react";

const fallbackApi = {
  health: async () => {
    const response = await fetch("http://127.0.0.1:8765/api/health");
    return response.json();
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
  const [prompt, setPrompt] = useState(
    "Summarize the purpose of this hybrid AI platform.",
  );
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    api()
      .health()
      .then((payload) => {
        if (isMounted) {
          setHealth(payload);
        }
      })
      .catch((caught) => {
        if (isMounted) {
          setError(caught.message);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  async function submitPrompt(event) {
    event.preventDefault();
    if (!prompt.trim()) {
      setError("Write a prompt first.");
      return;
    }

    setIsLoading(true);
    setError("");
    setAnswer(null);
    try {
      const payload = await api().chat({
        prompt,
        system_prompt: systemPrompt || undefined,
        temperature: Number(temperature),
        max_tokens: Number(maxTokens),
      });
      setAnswer(payload);
    } catch (caught) {
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
            A local desktop surface for Anthropic Claude through Amazon Bedrock,
            backed by the same Python runtime as the CLI.
          </p>
        </div>
        <StatusCard health={health} />
      </section>

      <section className="workspace">
        <form className="composer" onSubmit={submitPrompt}>
          <label htmlFor="prompt">Prompt</label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask the platform assistant..."
          />

          <label htmlFor="system-prompt">System prompt override</label>
          <input
            id="system-prompt"
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            placeholder="Optional"
          />

          <div className="controls">
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
            {isLoading ? "Thinking..." : "Run prompt"}
          </button>
        </form>

        <section className="response-panel">
          {error ? <div className="error">{error}</div> : null}
          {answer ? <ResponseCard answer={answer} /> : <EmptyState />}
        </section>
      </section>
    </main>
  );
}

function StatusCard({ health }) {
  return (
    <aside className="status-card">
      <span className="status-pill">{health ? "Connected" : "Starting"}</span>
      <dl>
        <div>
          <dt>Provider</dt>
          <dd>{health?.provider || "bedrock"}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{health?.aws_region || "pending"}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{health?.target_kind || "pending"}</dd>
        </div>
      </dl>
    </aside>
  );
}

function ResponseCard({ answer }) {
  return (
    <article className="answer-card">
      <div className="answer-meta">
        <span>{answer.provider}</span>
        <span>{answer.latency_ms} ms</span>
        <span>{answer.output_tokens ?? "?"} output tokens</span>
      </div>
      <p>{answer.response_text}</p>
      <details>
        <summary>Runtime details</summary>
        <pre>{JSON.stringify(answer, null, 2)}</pre>
      </details>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <p>Prompt results will appear here.</p>
      <span>The local Python API keeps credentials and Bedrock calls off the UI thread.</span>
    </div>
  );
}
