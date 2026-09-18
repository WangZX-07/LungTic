const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lungticConnection", Object.freeze({
  load: () => ipcRenderer.invoke("connection:load"),
  save: (connection) => ipcRenderer.invoke("connection:save", connection),
}));
