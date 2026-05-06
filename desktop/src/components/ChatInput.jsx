export default function ChatInput({
  prompt,
  isLoading,
  streamingMessageId,
  isBusy,
  onSetPrompt,
  onSubmit,
}) {
  return (
    <form className="composer" onSubmit={onSubmit}>
      <div className="composer-topline">
        <label htmlFor="prompt">Prompt</label>
        <p className="composer-note">
          Runtime settings live in the compact preferences panel.
        </p>
      </div>
      <textarea
        id="prompt"
        value={prompt}
        onChange={(event) => onSetPrompt(event.target.value)}
        onKeyDown={(event) => {
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
