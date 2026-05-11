import { formatRuntimeValue, formatTargetKind, formatTargetSource } from "../utils";

export default function PreferencesPanel({
  isControlsOpen,
  health,
  systemPrompt,
  temperature,
  maxTokens,
  isBusy,
  predictionEnabled,
  onSetSystemPrompt,
  onSetTemperature,
  onSetMaxTokens,
  onSetPredictionEnabled,
}) {
  return (
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
              onChange={(event) => onSetSystemPrompt(event.target.value)}
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
              onChange={(event) => onSetTemperature(event.target.value)}
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
              onChange={(event) => onSetMaxTokens(event.target.value)}
            />
          </label>
          <label className="panel-field panel-field-wide prediction-toggle">
            <span>Inline text prediction</span>
            <input
              type="checkbox"
              checked={predictionEnabled}
              onChange={(event) => onSetPredictionEnabled(event.target.checked)}
            />
          </label>
        </div>
      </div>
    </section>
  );
}
