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
