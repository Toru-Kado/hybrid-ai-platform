import { useEffect, useState } from "react";

/**
 * Non-intrusive banner that notifies the user when a new version is available.
 *
 * States:
 *   - idle / dismissed: hidden
 *   - available: shows version + Download button
 *   - downloading: shows progress percentage
 *   - ready: shows Restart button to apply the update
 */
export default function UpdateBanner() {
  const [state, setState] = useState("idle");
  const [version, setVersion] = useState(null);
  const [progress, setProgress] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!window.assistantApi?.onUpdateEvent) return;

    const cleanup = window.assistantApi.onUpdateEvent((event) => {
      switch (event.type) {
        case "available":
          setState("available");
          setVersion(event.version);
          setDismissed(false);
          break;
        case "not-available":
          setState("idle");
          break;
        case "download-progress":
          setState("downloading");
          setProgress(event.percent);
          break;
        case "downloaded":
          setState("ready");
          if (event.version) setVersion(event.version);
          break;
        case "error":
          // Silently revert to idle on error (graceful offline fallback).
          setState("idle");
          break;
      }
    });

    return cleanup;
  }, []);

  if (state === "idle" || dismissed) return null;

  return (
    <div className="update-banner" role="status" aria-live="polite">
      <div className="update-banner-content">
        {state === "available" && (
          <>
            <span className="update-banner-text">
              Version {version} is available.
            </span>
            <button
              type="button"
              className="secondary-button compact-button"
              onClick={() => window.assistantApi?.downloadUpdate()}
            >
              Download
            </button>
          </>
        )}
        {state === "downloading" && (
          <span className="update-banner-text">
            Downloading update... {progress}%
          </span>
        )}
        {state === "ready" && (
          <>
            <span className="update-banner-text">
              Update ready — restart to apply.
            </span>
            <button
              type="button"
              className="secondary-button compact-button"
              onClick={() => window.assistantApi?.installUpdate()}
            >
              Restart
            </button>
          </>
        )}
      </div>
      <button
        type="button"
        className="update-banner-dismiss"
        aria-label="Dismiss update notification"
        onClick={() => setDismissed(true)}
      >
        &times;
      </button>
    </div>
  );
}
