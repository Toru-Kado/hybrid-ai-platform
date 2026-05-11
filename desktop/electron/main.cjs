/**
 * Electron Main Process
 *
 * Orchestrates the desktop application lifecycle: spawns the Python backend
 * server as a child process, waits for it to become healthy, then creates the
 * renderer window. All renderer-to-backend communication is proxied through
 * IPC handlers defined here, keeping the renderer sandboxed from Node APIs.
 */
const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { buildAppMenu } = require("./menu.cjs");
const { initAutoUpdater } = require("./updater.cjs");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { resolveDesktopDbPath } = require("./db-path.cjs");
const { getSavedWindowBounds, saveWindowBounds } = require("./preferences.cjs");

app.name = "TK-AI";

// Backend API coordinates — kept on localhost so traffic never leaves the machine.
const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.HYBRID_AI_API_PORT || 8765);
const API_BASE_URL = `http://${API_HOST}:${API_PORT}`;

let mainWindow;
let backendProcess;

/** Returns the absolute path to the application icon PNG used for dock/taskbar. */
function iconPath() {
  return path.join(projectRoot(), "desktop", "assets", "app-icon.png");
}

/** Sets the macOS dock icon explicitly (no-op on other platforms or if icon is missing). */
function applyApplicationIcon() {
  const resolvedIconPath = iconPath();
  if (!fs.existsSync(resolvedIconPath)) {
    return;
  }

  if (process.platform === "darwin" && app.dock?.setIcon) {
    app.dock.setIcon(resolvedIconPath);
  }
}

/**
 * Resolves the project root directory.
 * In development this is the repo root; in a packaged build it is the asar archive root.
 */
function projectRoot() {
  return app.isPackaged
    ? app.getAppPath()
    : path.resolve(__dirname, "../..");
}

/**
 * Determines which Python executable to use for the backend server.
 * Priority: HYBRID_AI_PYTHON env override > project venv > system python.
 * For absolute paths (venv candidates) we verify the file exists; for bare
 * command names we optimistically accept the first one and let spawn fail later.
 */
function resolvePythonCommand(rootDir) {
  if (process.env.HYBRID_AI_PYTHON) {
    return process.env.HYBRID_AI_PYTHON;
  }

  const candidates =
    process.platform === "win32"
      ? [
          path.join(rootDir, ".venv", "Scripts", "python.exe"),
          "python",
          "py",
        ]
      : [
          path.join(rootDir, ".venv", "bin", "python"),
          "python3",
          "python",
        ];

  return candidates.find((candidate) => {
    return candidate.includes(path.sep) ? fs.existsSync(candidate) : true;
  });
}

/**
 * Spawns the Python API server as a child process.
 * The server runs on localhost and provides all AI/session/search endpoints.
 * PYTHONUNBUFFERED=1 ensures log output streams immediately for debugging.
 */
function startBackend() {
  const rootDir = projectRoot();
  const pythonCommand = resolvePythonCommand(rootDir);
  const envFile = process.env.HYBRID_AI_ENV_FILE || path.join(rootDir, ".env");
  const dbPath = resolveDesktopDbPath({
    envDbPath: process.env.HYBRID_AI_DB_PATH,
    isPackaged: app.isPackaged,
    projectRootPath: rootDir,
    userDataPath: app.getPath("userData"),
  });

  backendProcess = spawn(
    pythonCommand,
    [
      "-m",
      "app.server",
      "--host",
      API_HOST,
      "--port",
      String(API_PORT),
      "--env-file",
      envFile,
      "--db-path",
      dbPath,
    ],
    {
      cwd: rootDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  backendProcess.stdout.on("data", (chunk) => {
    console.log(`[assistant-api] ${chunk.toString().trim()}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    console.error(`[assistant-api] ${chunk.toString().trim()}`);
  });
  backendProcess.on("exit", (code) => {
    if (code && code !== 0) {
      console.error(`[assistant-api] exited with code ${code}`);
    }
  });
}

/**
 * Polls the backend health endpoint until it responds OK.
 * Gives the Python server up to 15 seconds to boot — this accounts for
 * cold-start time of the venv and SQLite schema migrations.
 */
async function waitForBackend() {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 15000) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`);
      if (response.ok) {
        return;
      }
    } catch (_error) {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error("The local assistant API did not start within 15 seconds.");
}

/**
 * Creates the main BrowserWindow with restored size/position from saved preferences.
 * In development, loads from the Vite dev server; in production, loads the built HTML.
 * Context isolation is enforced so the renderer cannot access Node directly.
 */
async function createWindow() {
  const savedBounds = getSavedWindowBounds();

  mainWindow = new BrowserWindow({
    width: savedBounds?.width || 1180,
    height: savedBounds?.height || 820,
    ...(savedBounds?.x !== undefined && { x: savedBounds.x }),
    ...(savedBounds?.y !== undefined && { y: savedBounds.y }),
    minWidth: 920,
    minHeight: 680,
    show: false,
    title: "TK-AI",
    backgroundColor: "#101816",
    icon: iconPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (savedBounds?.maximized) {
    mainWindow.maximize();
  }

  mainWindow.on("close", () => {
    saveWindowBounds(mainWindow);
  });

  buildAppMenu(mainWindow);

  mainWindow.once("ready-to-show", () => mainWindow.show());

  if (app.isPackaged || process.env.NODE_ENV === "test") {
    await mainWindow.loadFile(path.join(projectRoot(), "desktop", "dist", "index.html"));
  } else {
    await mainWindow.loadURL("http://127.0.0.1:5173");
  }
}

// ---------------------------------------------------------------------------
// IPC Handlers
// Each handler proxies a renderer request to the local Python API server.
// This keeps the renderer process sandboxed (no direct network/Node access).
// ---------------------------------------------------------------------------

ipcMain.handle("assistant:health", async () => {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  return response.json();
});

ipcMain.handle("assistant:listSessions", async () => {
  const response = await fetch(`${API_BASE_URL}/api/sessions`);
  return response.json();
});

ipcMain.handle("assistant:createSession", async (_event, payload) => {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload || {}),
  });
  return response.json();
});

ipcMain.handle("assistant:getSession", async (_event, sessionId) => {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to load session.");
  }
  return body;
});

ipcMain.handle("assistant:renameSession", async (_event, sessionId, payload) => {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload || {}),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to rename session.");
  }
  return body;
});

ipcMain.handle("assistant:deleteSession", async (_event, sessionId) => {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
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
  return null;
});

/** Presents a native Save dialog and writes transcript content to the chosen path. */
ipcMain.handle("assistant:saveTranscript", async (_event, payload) => {
  const format = payload?.format === "json" ? "json" : "markdown";
  const content = typeof payload?.content === "string" ? payload.content : "";
  const suggestedName =
    typeof payload?.suggestedName === "string" && payload.suggestedName.trim()
      ? payload.suggestedName.trim()
      : `session-transcript.${format === "json" ? "json" : "md"}`;
  const saveDialog = await dialog.showSaveDialog(mainWindow ?? undefined, {
    title: "Export session transcript",
    defaultPath: path.join(app.getPath("downloads"), suggestedName),
    filters:
      format === "json"
        ? [{ name: "JSON", extensions: ["json"] }]
        : [{ name: "Markdown", extensions: ["md", "markdown"] }],
  });

  if (saveDialog.canceled || !saveDialog.filePath) {
    return { canceled: true };
  }

  await fs.promises.writeFile(saveDialog.filePath, content, "utf8");
  return { canceled: false, path: saveDialog.filePath };
});

ipcMain.handle("assistant:chat", async (_event, payload) => {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Assistant request failed.");
  }
  return body;
});

ipcMain.handle("assistant:searchMessages", async (_event, query, options = {}) => {
  const params = new URLSearchParams({ q: query });
  if (options.sessionId) params.set("session_id", String(options.sessionId));
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));

  const response = await fetch(`${API_BASE_URL}/api/search?${params}`);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Search failed.");
  }
  return body;
});

ipcMain.handle("assistant:complete", async (_event, payload) => {
  const response = await fetch(`${API_BASE_URL}/api/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Completion request failed.");
  }
  return body;
});

ipcMain.handle("assistant:getAwsProfile", async () => {
  return process.env.AWS_PROFILE || null;
});

/**
 * Triggers an AWS SSO login flow by spawning the AWS CLI as a subprocess.
 * Required when the user's SSO session token has expired and Bedrock calls fail.
 */
ipcMain.handle("assistant:ssoLogin", async (_event, profileName) => {
  const profile = profileName || process.env.AWS_PROFILE;
  if (!profile) {
    throw new Error("No AWS profile configured for SSO login.");
  }

  return new Promise((resolve, reject) => {
    const loginProcess = spawn("aws", ["sso", "login", "--profile", profile], {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env },
    });

    let stderr = "";

    loginProcess.stdout.on("data", (chunk) => {
      console.log(`[aws-sso-login] ${chunk.toString().trim()}`);
    });
    loginProcess.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      console.error(`[aws-sso-login] ${chunk.toString().trim()}`);
    });

    loginProcess.on("exit", (code) => {
      if (code === 0) {
        resolve({ success: true, profile });
      } else {
        reject(
          new Error(
            `aws sso login failed (exit code ${code}): ${stderr.trim() || "Unknown error"}`,
          ),
        );
      }
    });

    loginProcess.on("error", (err) => {
      reject(new Error(`Failed to start aws sso login: ${err.message}`));
    });
  });
});

// ---------------------------------------------------------------------------
// Application Lifecycle
// ---------------------------------------------------------------------------

// Startup sequence: icon -> backend subprocess -> wait for health -> open window.
// When HYBRID_AI_SKIP_BACKEND=1, assume the backend is managed externally (e.g. tests).
app.whenReady().then(async () => {
  try {
    applyApplicationIcon();
    if (!process.env.HYBRID_AI_SKIP_BACKEND) {
      startBackend();
      await waitForBackend();
    }
    await createWindow();
    buildAppMenu(mainWindow);
    initAutoUpdater(mainWindow);
  } catch (error) {
    dialog.showErrorBox("TK-AI failed to start", String(error));
    app.quit();
  }
});

// On non-macOS platforms, closing all windows should quit the app.
// macOS convention keeps the app alive in the dock until explicitly quit.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

// macOS: re-create the window when the dock icon is clicked and no windows exist.
app.on("activate", async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await createWindow();
  }
});

// Ensure the Python backend subprocess is terminated when the app quits,
// preventing orphaned processes that would hold the port open.
app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
