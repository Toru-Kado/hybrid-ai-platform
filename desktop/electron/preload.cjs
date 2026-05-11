const { contextBridge, ipcRenderer } = require("electron");

const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.HYBRID_AI_API_PORT || 8765);
const API_BASE_URL = `http://${API_HOST}:${API_PORT}`;

contextBridge.exposeInMainWorld("assistantApi", {
  health: () => ipcRenderer.invoke("assistant:health"),
  listSessions: () => ipcRenderer.invoke("assistant:listSessions"),
  createSession: (payload) => ipcRenderer.invoke("assistant:createSession", payload),
  getSession: (sessionId) => ipcRenderer.invoke("assistant:getSession", sessionId),
  renameSession: (sessionId, payload) =>
    ipcRenderer.invoke("assistant:renameSession", sessionId, payload),
  deleteSession: (sessionId) => ipcRenderer.invoke("assistant:deleteSession", sessionId),
  saveTranscript: (payload) => ipcRenderer.invoke("assistant:saveTranscript", payload),
  chat: (payload) => ipcRenderer.invoke("assistant:chat", payload),
  streamChat: (payload, handlers) =>
    streamChatOverHttp(`${API_BASE_URL}/api/chat/stream`, payload, handlers),
  complete: (payload) => ipcRenderer.invoke("assistant:complete", payload),
  searchMessages: (query, options) =>
    ipcRenderer.invoke("assistant:searchMessages", query, options),
  getAwsProfile: () => ipcRenderer.invoke("assistant:getAwsProfile"),
  ssoLogin: (profileName) => ipcRenderer.invoke("assistant:ssoLogin", profileName),
  onMenuAction: (callback) => {
    const listener = (_event, action) => callback(action);
    ipcRenderer.on("menu:action", listener);
    return () => ipcRenderer.removeListener("menu:action", listener);
  },
});

async function streamChatOverHttp(url, payload, handlers = {}) {
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
