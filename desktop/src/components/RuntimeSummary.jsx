import { formatRuntimeValue, formatTargetKind } from "../utils";

export default function RuntimeSummary({ health }) {
  return (
    <div className="runtime-summary">
      <span className="status-pill">{health ? "Connected" : "Starting"}</span>
      <div className="runtime-summary-copy">
        <strong>{formatTargetKind(health?.target_kind)}</strong>
        <span>
          {formatRuntimeValue(health?.provider, "bedrock")} via{" "}
          {formatRuntimeValue(health?.aws_region, "us-east-1")}
        </span>
      </div>
    </div>
  );
}
