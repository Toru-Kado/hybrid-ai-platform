const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("assistantApi", {
  health: () => ipcRenderer.invoke("assistant:health"),
  listSessions: () => ipcRenderer.invoke("assistant:listSessions"),
  createSession: (payload) => ipcRenderer.invoke("assistant:createSession", payload),
  getSession: (sessionId) => ipcRenderer.invoke("assistant:getSession", sessionId),
  renameSession: (sessionId, payload) =>
    ipcRenderer.invoke("assistant:renameSession", sessionId, payload),
  deleteSession: (sessionId) => ipcRenderer.invoke("assistant:deleteSession", sessionId),
  chat: (payload) => ipcRenderer.invoke("assistant:chat", payload),
});
