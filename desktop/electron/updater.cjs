/**
 * Auto-Updater Module
 *
 * Encapsulates all update logic using electron-updater with GitHub Releases
 * as the update source. Provides non-blocking update checks on launch,
 * user-controlled download/install, and graceful offline fallback.
 *
 * Events forwarded to the renderer via IPC:
 *   - updater:event { type, payload }
 *
 * IPC handlers registered:
 *   - updater:checkForUpdates
 *   - updater:downloadUpdate
 *   - updater:installUpdate
 */
const { ipcMain } = require("electron");

let autoUpdater;

/**
 * Initializes the auto-updater for the given main window.
 * Sets up event listeners, IPC handlers, and schedules a delayed
 * startup check (5 seconds after launch) to avoid blocking the UI.
 *
 * In development mode (non-packaged app), the updater is not initialized
 * since updates only work with packaged builds.
 */
function initAutoUpdater(mainWindow) {
  // electron-updater only works in packaged builds; skip in dev to avoid errors.
  const { app } = require("electron");
  if (!app.isPackaged) {
    registerNoOpHandlers();
    return;
  }

  try {
    autoUpdater = require("electron-updater").autoUpdater;
  } catch (err) {
    console.error("[updater] Failed to load electron-updater:", err.message);
    registerNoOpHandlers();
    return;
  }

  // Do not download automatically — let the user opt in.
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  // Forward updater events to the renderer process.
  autoUpdater.on("checking-for-update", () => {
    sendUpdateEvent(mainWindow, { type: "checking" });
  });

  autoUpdater.on("update-available", (info) => {
    sendUpdateEvent(mainWindow, {
      type: "available",
      version: info.version,
      releaseNotes: info.releaseNotes || null,
    });
  });

  autoUpdater.on("update-not-available", () => {
    sendUpdateEvent(mainWindow, { type: "not-available" });
  });

  autoUpdater.on("download-progress", (progress) => {
    sendUpdateEvent(mainWindow, {
      type: "download-progress",
      percent: Math.round(progress.percent),
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    sendUpdateEvent(mainWindow, {
      type: "downloaded",
      version: info.version,
    });
  });

  autoUpdater.on("error", (err) => {
    console.error("[updater] Error:", err.message);
    sendUpdateEvent(mainWindow, {
      type: "error",
      message: err.message,
    });
  });

  // Register IPC handlers for renderer-initiated actions.
  ipcMain.handle("updater:checkForUpdates", async () => {
    if (!autoUpdater) return null;
    try {
      return await autoUpdater.checkForUpdates();
    } catch (err) {
      console.error("[updater] Check failed:", err.message);
      return null;
    }
  });

  ipcMain.handle("updater:downloadUpdate", async () => {
    if (!autoUpdater) return null;
    try {
      return await autoUpdater.downloadUpdate();
    } catch (err) {
      console.error("[updater] Download failed:", err.message);
      return null;
    }
  });

  ipcMain.handle("updater:installUpdate", () => {
    if (!autoUpdater) return;
    autoUpdater.quitAndInstall();
  });

  // Schedule an automatic check 5 seconds after launch.
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.error("[updater] Startup check failed:", err.message);
    });
  }, 5000);
}

/**
 * Triggers a manual check for updates (e.g. from the Help menu).
 * Forwards the "checking" event and performs the check; errors are
 * forwarded as updater events rather than thrown.
 */
function checkForUpdatesManually(mainWindow) {
  if (!autoUpdater) {
    sendUpdateEvent(mainWindow, { type: "not-available" });
    return;
  }
  autoUpdater.checkForUpdates().catch((err) => {
    console.error("[updater] Manual check failed:", err.message);
  });
}

/**
 * Registers no-op IPC handlers so renderer calls don't throw
 * when running in development mode or if electron-updater fails to load.
 */
function registerNoOpHandlers() {
  ipcMain.handle("updater:checkForUpdates", async () => null);
  ipcMain.handle("updater:downloadUpdate", async () => null);
  ipcMain.handle("updater:installUpdate", () => {});
}

/** Sends an updater event payload to the renderer via IPC. */
function sendUpdateEvent(mainWindow, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("updater:event", payload);
  }
}

module.exports = { initAutoUpdater, checkForUpdatesManually };
