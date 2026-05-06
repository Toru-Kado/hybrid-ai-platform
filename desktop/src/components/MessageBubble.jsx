import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { formatTimestamp } from "../utils";

export default function MessageBubble({
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
