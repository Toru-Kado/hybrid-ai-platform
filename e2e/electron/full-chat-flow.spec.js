/**
 * Electron E2E test: full chat flow.
 * Verifies the complete user journey: create session, send message,
 * receive streamed response, and verify persistence across navigation.
 */

import { test, expect } from "@playwright/test";
import { _electron as electron } from "playwright";
import path from "node:path";

const PROJECT_ROOT = path.resolve(import.meta.dirname, "../..");

test.describe("Full chat flow", () => {
  let electronApp;
  let window;

  test.beforeAll(async () => {
    electronApp = await electron.launch({
      args: [path.join(PROJECT_ROOT, "desktop", "electron", "main.cjs")],
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        NODE_ENV: "test",
        HYBRID_AI_API_PORT: "0",
      },
    });

    window = await electronApp.firstWindow();
    await window.waitForSelector(".chat-layout", { timeout: 30000 });
  });

  test.afterAll(async () => {
    if (electronApp) {
      await electronApp.close();
    }
  });

  test("sends a message and receives a streamed response", async () => {
    const promptInput = window.locator("#prompt");
    await promptInput.fill("Hello from Electron E2E");

    await window.locator('.composer button[type="submit"]').click();

    // Wait for the response in the thread
    const thread = window.locator('[role="log"]');
    await expect(thread).toContainText("Hello from Electron E2E", {
      timeout: 15000,
    });
    await expect(thread).toContainText("echo:", { timeout: 15000 });
  });

  test("session appears in sidebar after sending message", async () => {
    const sidebar = window.locator("aside.sidebar");
    await expect(sidebar.locator(".session-item")).toHaveCount(1, {
      timeout: 10000,
    });
  });

  test("creates a new session and navigates back", async () => {
    // Create a new session
    await window.locator("aside.sidebar").getByText("New chat").click();

    const promptInput = window.locator("#prompt");
    await promptInput.fill("Second session message");
    await window.locator('.composer button[type="submit"]').click();

    const thread = window.locator('[role="log"]');
    await expect(thread).toContainText("echo: Second session message", {
      timeout: 15000,
    });

    // Two sessions should exist
    const sidebar = window.locator("aside.sidebar");
    await expect(sidebar.locator(".session-item")).toHaveCount(2, {
      timeout: 10000,
    });

    // Navigate back to first session
    await sidebar
      .locator(".session-item")
      .filter({ hasText: "Hello from Electron" })
      .click();

    // First session's content should be restored
    await expect(thread).toContainText("Hello from Electron E2E", {
      timeout: 10000,
    });
  });

  test("persists messages after session navigation", async () => {
    // We're on the first session from the previous test
    const thread = window.locator('[role="log"]');

    // Should still see the original message and response
    await expect(thread).toContainText("Hello from Electron E2E");
    await expect(thread).toContainText("echo:");
  });
});
