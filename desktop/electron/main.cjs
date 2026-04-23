const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const API_HOST = "127.0.0.1";
const API_PORT = Number(process.env.HYBRID_AI_API_PORT || 8765);
const API_BASE_URL = `http://${API_HOST}:${API_PORT}`;

let mainWindow;
let backendProcess;

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

app.whenReady().then(async () => {
  try {
    startBackend();
    await waitForBackend();
    await createWindow();
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
