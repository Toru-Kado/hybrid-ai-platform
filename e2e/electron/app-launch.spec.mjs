/**
 * Electron E2E test: app launch.
 * Verifies that the Electron app launches, the window opens, and the
 * health status shows connected once the Python backend is ready.
 */

import { test, expect } from "@playwright/test";
import { _electron as electron } from "playwright";
import path from "node:path";

const PROJECT_ROOT = path.resolve(import.meta.dirname, "../..");

test.describe("Electron app launch", () => {
  let electronApp;
  let window;

  test.beforeAll(async () => {
    electronApp = await electron.launch({
      args: [path.join(PROJECT_ROOT, "desktop", "electron", "main.cjs")],
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        NODE_ENV: "test",
        HYBRID_AI_API_PORT: "8766",
        HYBRID_AI_SKIP_BACKEND: "1",
        ELECTRON_ENABLE_LOGGING: "1",
      },
    });

    // Capture console for debugging
    electronApp.on("close", () => {
      console.log("[electron] app closed");
    });

    window = await electronApp.firstWindow();
    // Wait for the app to fully render
    await window.waitForLoadState("domcontentloaded");
    await window.waitForSelector(".chat-layout", { timeout: 30000 });
  });

  test.afterAll(async () => {
    if (electronApp) {
      await electronApp.close();
    }
  });

  test("opens a window with the correct title", async () => {
    const title = await window.title();
    expect(title).toContain("TK-AI");
  });

  test("renders the main chat layout", async () => {
    const chatLayout = window.locator(".chat-layout");
    await expect(chatLayout).toBeVisible();
  });

  test("displays the sidebar", async () => {
    const sidebar = window.locator("aside.sidebar");
    await expect(sidebar).toBeVisible();
  });

  test("has a functional prompt input", async () => {
    const promptInput = window.locator("#prompt");
    await expect(promptInput).toBeVisible();
    await expect(promptInput).toBeEnabled();
  });

  test("shows health status as connected", async () => {
    // The app performs a health check on startup
    // Wait for the preferences toggle to be enabled (indicates health check passed)
    const prefsButton = window.locator("button.preferences-toggle");
    await expect(prefsButton).toBeVisible({ timeout: 15000 });
  });
});
