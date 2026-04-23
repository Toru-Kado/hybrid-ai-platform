const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("assistantApi", {
  health: () => ipcRenderer.invoke("assistant:health"),
  chat: (payload) => ipcRenderer.invoke("assistant:chat", payload),
});
