/**
 * @file Thread state placeholder card — displayed when the message thread is
 * empty, loading, or in an error state. Provides a title, explanatory body
 * text, optional tone colouring (neutral/warning), and an optional action button.
 */

export default function ThreadStateCard({ title, body, tone = "neutral", actionLabel = null, onAction = null }) {
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
