export default function ChatInput({
  prompt,
  isLoading,
  streamingMessageId,
  isBusy,
  onSetPrompt,
  onSubmit,
  suggestion,
  onAcceptFull,
  onAcceptWord,
  onDismiss,
}) {
  return (
    <form className="composer" onSubmit={onSubmit}>
      <div className="composer-topline">
        <label htmlFor="prompt">Prompt</label>
        <p className="composer-note">
          Runtime settings live in the compact preferences panel.
        </p>
      </div>
      <div className="composer-input-wrapper">
        <textarea
          id="prompt"
          value={prompt}
          onChange={(event) => onSetPrompt(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Tab" && suggestion) {
              event.preventDefault();
              const accepted = onAcceptFull();
              if (accepted) onSetPrompt(prompt + accepted);
              return;
            }
            if (
              event.key === "ArrowRight" &&
              (event.ctrlKey || event.altKey) &&
              suggestion
            ) {
              event.preventDefault();
              const word = onAcceptWord();
              if (word) onSetPrompt(prompt + word);
              return;
            }
            if (event.key === "Escape" && suggestion) {
              event.preventDefault();
              onDismiss();
              return;
            }
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!isBusy && prompt.trim()) {
                onSubmit(event);
              }
            }
          }}
          disabled={isBusy}
          placeholder="Ask the platform assistant..."
        />
        {suggestion && (
          <div className="ghost-text" aria-hidden="true">
            <span className="ghost-text-prefix">{prompt}</span>
            <span className="ghost-text-suggestion">{suggestion}</span>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={isBusy}
        aria-disabled={isBusy}
        title={isBusy ? "Waiting for the current response to complete" : undefined}
      >
        {isLoading ? "Thinking..." : streamingMessageId ? "Streaming..." : "Send message"}
      </button>
    </form>
  );
}
