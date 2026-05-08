const { app, screen } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const PREFS_FILENAME = "preferences.json";

function prefsPath() {
  return path.join(app.getPath("userData"), PREFS_FILENAME);
}

function loadPreferences() {
  try {
    const raw = fs.readFileSync(prefsPath(), "utf8");
    return JSON.parse(raw);
  } catch (_error) {
    return {};
  }
}

function savePreferences(data) {
  try {
    fs.writeFileSync(prefsPath(), JSON.stringify(data, null, 2), "utf8");
  } catch (_error) {
    // Non-critical — silently skip if write fails
  }
}

function getSavedWindowBounds() {
  const prefs = loadPreferences();
  const saved = prefs.window;
  if (!saved || typeof saved.width !== "number" || typeof saved.height !== "number") {
    return null;
  }

  const bounds = {
    width: Math.max(saved.width, 920),
    height: Math.max(saved.height, 680),
    maximized: saved.maximized === true,
  };

  if (typeof saved.x === "number" && typeof saved.y === "number") {
    const testRect = { x: saved.x, y: saved.y, width: bounds.width, height: bounds.height };
    const display = screen.getDisplayMatching(testRect);
    const { x, y, width, height } = display.workArea;
    const isOnScreen =
      saved.x >= x - bounds.width + 100 &&
      saved.x <= x + width - 100 &&
      saved.y >= y &&
      saved.y <= y + height - 100;

    if (isOnScreen) {
      bounds.x = saved.x;
      bounds.y = saved.y;
    }
  }

  return bounds;
}

function saveWindowBounds(browserWindow) {
  const isMaximized = browserWindow.isMaximized();
  const bounds = isMaximized ? browserWindow.getNormalBounds() : browserWindow.getBounds();
  const prefs = loadPreferences();
  prefs.window = {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    maximized: isMaximized,
  };
  savePreferences(prefs);
}

module.exports = { loadPreferences, savePreferences, getSavedWindowBounds, saveWindowBounds };
