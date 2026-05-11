/**
 * Window Bounds Persistence
 *
 * Saves and restores the main window's position, size, and maximized state
 * across app restarts. The preferences file is stored in Electron's userData
 * directory (platform-specific). On restore, saved coordinates are validated
 * against current display geometry to avoid placing the window off-screen
 * (e.g., after disconnecting an external monitor).
 */
const { app, screen } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const PREFS_FILENAME = "preferences.json";

/** Returns the absolute path to the JSON preferences file in user app data. */
function prefsPath() {
  return path.join(app.getPath("userData"), PREFS_FILENAME);
}

/** Reads and parses the preferences file. Returns empty object on any failure. */
function loadPreferences() {
  try {
    const raw = fs.readFileSync(prefsPath(), "utf8");
    return JSON.parse(raw);
  } catch (_error) {
    return {};
  }
}

/** Atomically writes the full preferences object to disk. Failures are non-fatal. */
function savePreferences(data) {
  try {
    fs.writeFileSync(prefsPath(), JSON.stringify(data, null, 2), "utf8");
  } catch (_error) {
    // Non-critical — silently skip if write fails
  }
}

/**
 * Retrieves previously saved window bounds, enforcing minimum dimensions and
 * verifying that the saved position is still visible on a connected display.
 * Returns null if no valid saved state exists (window will use defaults).
 */
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

  // Validate that the saved position lands on a currently connected display.
  // If the window would be mostly off-screen, omit x/y so Electron centers it.
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

/**
 * Captures the current window geometry and persists it for next launch.
 * If maximized, stores the "normal" (restored) bounds so un-maximizing
 * returns to a sensible size rather than whatever the maximized frame was.
 */
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
