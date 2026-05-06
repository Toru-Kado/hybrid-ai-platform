export default function ErrorBanner({ errorState, onRetry, onDismiss }) {
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
