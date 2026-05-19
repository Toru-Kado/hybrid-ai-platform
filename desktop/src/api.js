import { fetchWithRetry } from "./retry";
import { transcriptFormatConfig } from "./transcript";
import { AUTH_ENABLED, getAccessToken, refreshSession } from "./auth";

const API_PORT = import.meta.env.VITE_API_PORT || 8765;
const isWebMode = !window.assistantApi && AUTH_ENABLED;
const API_BASE = isWebMode
  ? (import.meta.env.VITE_API_BASE_URL || "")
  : `http://127.0.0.1:${API_PORT}`;

async function getAuthHeaders() {
  if (!AUTH_ENABLED) return {};
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchWithAuth(url, options = {}) {
  const authHeaders = await getAuthHeaders();
  const merged = {
    ...options,
    headers: { ...(options.headers || {}), ...authHeaders },
  };
  const response = await fetchWithRetry(url, merged);
  if (response.status === 401 && AUTH_ENABLED) {
    const refreshed = await refreshSession();
    if (refreshed) {
      const newHeaders = await getAuthHeaders();
      return fetchWithRetry(url, {
        ...options,
        headers: { ...(options.headers || {}), ...newHeaders },
      });
    }
  }
  return response;
}

function parseSseChunk(chunk) {
  const lines = chunk.split("\n");
  let type = "message";
  const dataLines = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line) {
      continue;
    }
    if (line.startsWith("event:")) {
      type = line.slice("event:".length).trim() || "message";
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    type,
    payload: JSON.parse(dataLines.join("\n")),
  };
}

export async function streamChatOverHttp(url, payload, handlers = {}) {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.error || "Assistant request failed.");
  }

  if (!response.body) {
    throw new Error("Streaming is not available in this environment.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const event = parseSseChunk(chunk);
      if (!event) {
        continue;
      }
      if (event.type === "session" && event.payload?.session) {
        await handlers.onSession?.(event.payload.session);
        continue;
      }
      if (event.type === "user_message" && event.payload?.message) {
        await handlers.onUserMessage?.(event.payload.message);
        continue;
      }
      if (event.type === "delta" && typeof event.payload?.text === "string") {
        await handlers.onTextDelta?.(event.payload.text);
        continue;
      }
      if (event.type === "complete" && event.payload) {
        await handlers.onComplete?.(event.payload);
        return event.payload;
      }
      if (event.type === "error") {
        throw new Error(event.payload?.error || "Assistant request failed.");
      }
    }

    if (done) {
      // Process any remaining buffered data (final event may lack trailing \n\n)
      if (buffer.trim()) {
        const event = parseSseChunk(buffer);
        if (event) {
          if (event.type === "complete" && event.payload) {
            await handlers.onComplete?.(event.payload);
            return event.payload;
          }
          if (event.type === "error") {
            throw new Error(event.payload?.error || "Assistant request failed.");
          }
        }
      }
      break;
    }
  }

  throw new Error("Assistant stream ended unexpectedly.");
}

const fallbackApi = {
  health: async () => {
    const response = await fetchWithAuth(`${API_BASE}/api/health`);
    return response.json();
  },
  listSessions: async () => {
    const response = await fetchWithAuth(`${API_BASE}/api/sessions`);
    return response.json();
  },
  createSession: async (payload) => {
    const response = await fetchWithAuth(`${API_BASE}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    return response.json();
  },
  getSession: async (sessionId) => {
    const response = await fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to load session.");
    }
    return body;
  },
  renameSession: async (sessionId, payload) => {
    const response = await fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to rename session.");
    }
    return body;
  },
  deleteSession: async (sessionId) => {
    const response = await fetchWithAuth(`${API_BASE}/api/sessions/${sessionId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      let body = {};
      try {
        body = await response.json();
      } catch (_error) {
        body = {};
      }
      throw new Error(body.error || "Failed to delete session.");
    }
  },
  saveTranscript: async (payload) => {
    const config = transcriptFormatConfig(payload?.format);
    const blob = new Blob([payload?.content || ""], { type: config.mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = payload?.suggestedName || `session-transcript.${config.extension}`;
    link.click();
    URL.revokeObjectURL(url);
    return { canceled: false, path: link.download };
  },
  complete: async (payload) => {
    const response = await fetchWithAuth(`${API_BASE}/api/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Completion request failed.");
    }
    return body;
  },
  searchMessages: async (query, options = {}) => {
    const params = new URLSearchParams({ q: query });
    if (options.sessionId) params.set("session_id", String(options.sessionId));
    if (options.limit) params.set("limit", String(options.limit));
    if (options.offset) params.set("offset", String(options.offset));
    const response = await fetchWithAuth(
      `${API_BASE}/api/search?${params}`
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Search failed.");
    }
    return body;
  },
  streamChat: async (payload, handlers) => {
    return streamChatOverHttp(`${API_BASE}/api/chat/stream`, payload, handlers);
  },
};

export function api() {
  return window.assistantApi || fallbackApi;
}

export function streamChatApi() {
  if (window.assistantApi?.streamChat) {
    return window.assistantApi.streamChat;
  }
  return fallbackApi.streamChat;
}
