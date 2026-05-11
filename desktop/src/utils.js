/**
 * @file Shared utility functions for the desktop frontend.
 *
 * Contains session-list manipulation helpers, timestamp formatting, error
 * classification/display logic, clipboard access, and runtime-value formatters.
 */

/**
 * Upserts a session into the list: removes any existing entry with the same ID
 * and prepends the new session at the top (most-recently-active first).
 * @param {Array} current - Current sessions array.
 * @param {object} session - Session to merge in.
 * @returns {Array} Updated sessions array.
 */
export function mergeSession(current, session) {
  const existing = current.filter((item) => item.session_id !== session.session_id);
  return [session, ...existing];
}

/**
 * Replaces an existing session in-place (by session_id) without reordering.
 * Used after rename operations where position should remain stable.
 * @param {Array} current - Current sessions array.
 * @param {object} session - Updated session object.
 * @returns {Array} New array with the matching session replaced.
 */
export function replaceSession(current, session) {
  return current.map((item) => (item.session_id === session.session_id ? session : item));
}

/**
 * Formats an ISO timestamp into a short locale time string (e.g. "3:45 PM").
 * @param {string} value - ISO 8601 date string.
 * @returns {string} Formatted time or empty string on failure.
 */
export function formatTimestamp(value) {
  try {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch (_error) {
    return "";
  }
}

/**
 * Returns a runtime value if it is a non-empty string, otherwise a fallback.
 * @param {*} value - Value to check.
 * @param {string} fallback - Default to return when value is empty/missing.
 * @returns {string}
 */
export function formatRuntimeValue(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

/**
 * Constructs a structured error state object from a raw error message.
 * Classifies the error, selects a user-facing title and hint, and attaches
 * retry metadata so the UI can offer contextual recovery actions.
 * @param {string} message - Raw error message text.
 * @param {{ context?: string, retry?: object }} [options] - Context and retry info.
 * @returns {{ context: string, category: string, title: string, message: string, hint: string|null, retry: object|null }}
 */
export function buildErrorState(message, options = {}) {
  const context = options.context || "general";
  const normalizedMessage =
    typeof message === "string" && message.trim()
      ? message.trim()
      : "Unexpected desktop application error.";
  const category = classifyErrorCategory(normalizedMessage);

  return {
    context,
    category,
    title: errorTitleFor(category, context),
    message: normalizedMessage,
    hint: errorHintFor(category, context),
    retry: options.retry || null,
  };
}

/**
 * Classifies an error message into one of: "auth", "network", "provider", or "general".
 * Uses regex pattern matching against common error signatures from AWS, network
 * stack, and AI provider responses.
 * @param {string} message - Error message to classify.
 * @returns {"auth"|"network"|"provider"|"general"}
 */
export function classifyErrorCategory(message) {
  if (
    /accessdenied|unauthoriz|expiredtoken|expired.*token|token.*expired|security token|credentials|credential|aws auth|aws sso|sso login|retrieving token.*sso|assume role|not authorized/i.test(
      message,
    )
  ) {
    return "auth";
  }
  if (
    /network|timed out|timeout|could not reach|failed to fetch|econn|connection refused|connection reset|offline|did not start within/i.test(
      message,
    )
  ) {
    return "network";
  }
  if (/bedrock|anthropic|provider|throttl|quota|guardrail|validation|model/i.test(message)) {
    return "provider";
  }
  return "general";
}

function errorTitleFor(category, context) {
  if (context === "history" && category !== "auth") {
    return "Could not load this session";
  }
  if (category === "auth") {
    return "AWS authentication needed";
  }
  if (category === "network") {
    return context === "bootstrap" ? "Connection problem" : "Network problem";
  }
  if (category === "provider") {
    return context === "prompt" ? "Provider request failed" : "Provider unavailable";
  }
  if (context === "bootstrap") {
    return "Desktop startup failed";
  }
  return "Something went wrong";
}

function errorHintFor(category, context) {
  if (category === "auth") {
    return "Refresh the active AWS session, then retry. If you use SSO, run aws sso login for the selected profile.";
  }
  if (category === "network") {
    return context === "bootstrap"
      ? "The local assistant API may still be starting, or the desktop app could not reach it."
      : "Check the local API connection and retry once the runtime is reachable again.";
  }
  if (category === "provider") {
    return "The request reached the configured provider path, but the model runtime could not complete it.";
  }
  return null;
}

/**
 * Formats the runtime target kind (e.g. "inference_profile") into a human-readable label.
 * @param {string} value - Raw target_kind string from the health endpoint.
 * @returns {string} Title-cased, space-separated label.
 */
export function formatTargetKind(value) {
  return humanizeRuntimeToken(formatRuntimeValue(value, "inference_profile"));
}

/**
 * Formats the runtime target source for display, with a pending-state fallback.
 * @param {string} value - Raw target_source from the health endpoint.
 * @returns {string}
 */
export function formatTargetSource(value) {
  return formatRuntimeValue(value, "Runtime target pending");
}

/**
 * Converts a snake_case or kebab-case token into a Title Case label.
 * @param {string} value - Token string (e.g. "inference_profile").
 * @returns {string} Human-readable label (e.g. "Inference Profile").
 */
export function humanizeRuntimeToken(value) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Copies a string value to the system clipboard. Uses the modern Clipboard API
 * when available, falling back to a hidden textarea + execCommand for older
 * environments (Electron on some platforms).
 * @param {string} value - Text to copy.
 * @returns {Promise<void>}
 * @throws {Error} If clipboard access is completely unavailable.
 */
export async function writeToClipboard(value) {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const success = document.execCommand("copy");
  document.body.removeChild(textarea);

  if (!success) {
    throw new Error("Clipboard access is unavailable in this environment.");
  }
}

/**
 * Finds the most recent assistant response and the user prompt that triggered it.
 * Scans from the end of the message list backward. Used to enable the
 * "regenerate" action on the latest assistant reply.
 * @param {Array} messages - Full message array for the active session.
 * @returns {{ assistantMessage: object, userMessage: object }|null}
 */
export function findLatestAssistantPair(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const assistantMessage = messages[index];
    if (assistantMessage?.role !== "assistant") {
      continue;
    }
    for (let candidate = index - 1; candidate >= 0; candidate -= 1) {
      const userMessage = messages[candidate];
      if (userMessage?.role === "user") {
        return { assistantMessage, userMessage };
      }
    }
    break;
  }
  return null;
}
