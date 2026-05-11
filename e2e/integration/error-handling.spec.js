/**
 * Integration test: error handling.
 * Verifies that the UI handles various states gracefully.
 */

import { test, expect } from "@playwright/test";

test.describe("Error handling", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".chat-layout");
  });

  test("does not send when prompt is empty", async ({ page }) => {
    const submitButton = page.locator('.composer button[type="submit"]');
    const promptInput = page.locator("#prompt");
    const thread = page.locator('[role="log"]');

    await expect(promptInput).toHaveValue("");

    // Count existing messages before attempting submit
    const initialCount = await thread.locator("article.message").count();

    // Click submit with empty prompt
    await submitButton.click();

    // No new message should appear (form prevents empty submit)
    await page.waitForTimeout(500);
    await expect(thread.locator("article.message")).toHaveCount(initialCount);
  });

  test("app is functional with API server connected", async ({ page }) => {
    // Wait for health check to complete
    await page.waitForTimeout(2000);

    // Prompt should be enabled
    const promptInput = page.locator("#prompt");
    await expect(promptInput).toBeEnabled();
  });

  test("recovers after sequential requests", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    const thread = page.locator('[role="log"]');

    // First message
    await promptInput.fill("first successful message");
    await page.locator('.composer button[type="submit"]').click();
    await expect(thread).toContainText("echo: first successful message", {
      timeout: 10000,
    });

    // Second message works
    await promptInput.fill("second successful message");
    await page.locator('.composer button[type="submit"]').click();
    await expect(thread).toContainText("echo: second successful message", {
      timeout: 10000,
    });
  });

  test("submit button re-enables after response completes", async ({
    page,
  }) => {
    const promptInput = page.locator("#prompt");
    const submitButton = page.locator('.composer button[type="submit"]');
    const thread = page.locator('[role="log"]');

    await promptInput.fill("test re-enable");
    await submitButton.click();

    await expect(thread).toContainText("echo: test re-enable", {
      timeout: 10000,
    });
    await expect(submitButton).toBeEnabled({ timeout: 5000 });

    // Should be able to send another message
    await promptInput.fill("follow-up message");
    await submitButton.click();
    await expect(thread).toContainText("echo: follow-up message", {
      timeout: 10000,
    });
  });
});
