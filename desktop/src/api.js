import { fetchWithRetry } from "./retry";
import { transcriptFormatConfig } from "./transcript";

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
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
      break;
    }
  }

  throw new Error("Assistant stream ended unexpectedly.");
}

const fallbackApi = {
  health: async () => {
    const response = await fetchWithRetry("http://127.0.0.1:8765/api/health");
    return response.json();
  },
  listSessions: async () => {
    const response = await fetchWithRetry("http://127.0.0.1:8765/api/sessions");
    return response.json();
  },
  createSession: async (payload) => {
    const response = await fetchWithRetry("http://127.0.0.1:8765/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    return response.json();
  },
  getSession: async (sessionId) => {
    const response = await fetchWithRetry(`http://127.0.0.1:8765/api/sessions/${sessionId}`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to load session.");
    }
    return body;
  },
  renameSession: async (sessionId, payload) => {
    const response = await fetchWithRetry(`http://127.0.0.1:8765/api/sessions/${sessionId}`, {
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
    const response = await fetchWithRetry(`http://127.0.0.1:8765/api/sessions/${sessionId}`, {
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
  streamChat: async (payload, handlers) => {
    return streamChatOverHttp("http://127.0.0.1:8765/api/chat/stream", payload, handlers);
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
