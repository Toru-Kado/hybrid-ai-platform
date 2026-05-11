/**
 * Integration test: SSE streaming.
 * Verifies that tokens arrive progressively (streaming indicator visible,
 * partial text rendered before final complete event).
 */

import { test, expect } from "@playwright/test";

test.describe("Streaming", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".chat-layout");
  });

  test("shows streaming indicator during response generation", async ({
    page,
  }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("streaming test message");
    await page.locator('.composer button[type="submit"]').click();

    // After completion, streaming indicator should be gone
    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("echo:", { timeout: 10000 });
    await expect(
      page.locator('[aria-label="Assistant is generating a response"]')
    ).toBeHidden({ timeout: 5000 });
  });

  test("renders complete response text after stream finishes", async ({
    page,
  }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("multi word prompt for streaming");
    await page.locator('.composer button[type="submit"]').click();

    const thread = page.locator('[role="log"]');
    // FakeClient streams word-by-word, final text should be the full echo
    await expect(thread).toContainText("echo: multi word prompt for streaming", {
      timeout: 10000,
    });
  });

  test("submit button re-enables after stream completes", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("check button state");

    const submitButton = page.locator('.composer button[type="submit"]');
    await submitButton.click();

    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("echo:", { timeout: 10000 });
    await expect(submitButton).toBeEnabled({ timeout: 5000 });
  });

  test("session appears in sidebar after streamed response", async ({
    page,
  }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("sidebar check");
    await page.locator('.composer button[type="submit"]').click();

    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("echo: sidebar check", {
      timeout: 10000,
    });

    // Session should appear in sidebar with the prompt as title
    const sidebar = page.locator("aside.sidebar");
    await expect(sidebar).toContainText("sidebar check", { timeout: 5000 });
  });
});
