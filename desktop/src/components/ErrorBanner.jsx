/**
 * @file Error alert banner — displays categorised errors with retry actions.
 *
 * Renders a role="alert" section colour-coded by error category (auth,
 * network, provider, general). Shows the error title, raw message, an
 * optional recovery hint, and contextual action buttons (retry / dismiss).
 */

export default function ErrorBanner({ errorState, onRetry, onDismiss }) {
  return (
    <section className={`status-banner status-banner-${errorState.category}`} role="alert" aria-live="assertive">
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
