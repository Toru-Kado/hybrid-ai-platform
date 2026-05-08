export function mergeSession(current, session) {
  const existing = current.filter((item) => item.session_id !== session.session_id);
  return [session, ...existing];
}

export function replaceSession(current, session) {
  return current.map((item) => (item.session_id === session.session_id ? session : item));
}

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

export function formatRuntimeValue(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

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

export function formatTargetKind(value) {
  return humanizeRuntimeToken(formatRuntimeValue(value, "inference_profile"));
}

export function formatTargetSource(value) {
  return formatRuntimeValue(value, "Runtime target pending");
}

export function humanizeRuntimeToken(value) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

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
