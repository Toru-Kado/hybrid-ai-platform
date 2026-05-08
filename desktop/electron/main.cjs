const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { buildAppMenu } = require("./menu.cjs");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { resolveDesktopDbPath } = require("./db-path.cjs");

const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.HYBRID_AI_API_PORT || 8765);
const API_BASE_URL = `http://${API_HOST}:${API_PORT}`;

let mainWindow;
let backendProcess;

function iconPath() {
  return path.join(projectRoot(), "desktop", "assets", "app-icon.png");
}

function applyApplicationIcon() {
  const resolvedIconPath = iconPath();
  if (!fs.existsSync(resolvedIconPath)) {
    return;
  }

  if (process.platform === "darwin" && app.dock?.setIcon) {
    app.dock.setIcon(resolvedIconPath);
  }
}

function projectRoot() {
  return app.isPackaged
    ? app.getAppPath()
    : path.resolve(__dirname, "../..");
}

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

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 920,
    minHeight: 680,
    show: false,
    title: "Hybrid AI Platform",
    backgroundColor: "#101816",
    icon: iconPath(),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());

  if (app.isPackaged) {
    await mainWindow.loadFile(path.join(projectRoot(), "desktop", "dist", "index.html"));
  } else {
    await mainWindow.loadURL("http://127.0.0.1:5173");
  }
}

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

ipcMain.handle("assistant:getAwsProfile", async () => {
  return process.env.AWS_PROFILE || null;
});

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

app.whenReady().then(async () => {
  try {
    applyApplicationIcon();
    startBackend();
    await waitForBackend();
    await createWindow();
    buildAppMenu(mainWindow);
  } catch (error) {
    dialog.showErrorBox("Hybrid AI Platform failed to start", String(error));
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await createWindow();
  }
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
