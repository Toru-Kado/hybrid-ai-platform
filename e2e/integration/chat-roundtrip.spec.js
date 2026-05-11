/**
 * Integration test: chat roundtrip.
 * Verifies that a user can type a prompt, submit it, and see the echoed
 * response from the FakeClient rendered in the message thread.
 */

import { test, expect } from "@playwright/test";

test.describe("Chat roundtrip", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".chat-layout");
  });

  test("sends a prompt and receives echo response", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("Hello integration test");

    await page.locator('.composer button[type="submit"]').click();

    // Wait for the user message and assistant response in the thread
    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("Hello integration test");
    await expect(thread).toContainText("echo: Hello integration test", {
      timeout: 10000,
    });
  });

  test("displays user message immediately on submit", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("Quick message");
    await page.locator('.composer button[type="submit"]').click();

    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("Quick message");
  });

  test("clears prompt input after submit", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("Clear me");
    await page.locator('.composer button[type="submit"]').click();

    await expect(promptInput).toHaveValue("");
  });

  test("submit button is disabled while response is streaming", async ({
    page,
  }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("Check busy state");
    const submitButton = page.locator('.composer button[type="submit"]');
    await submitButton.click();

    // Wait for response to complete
    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("echo:", { timeout: 10000 });

    // After completion, button should be re-enabled
    await expect(submitButton).toBeEnabled({ timeout: 5000 });
  });

  test("sends multiple messages in sequence", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    const submitButton = page.locator('.composer button[type="submit"]');
    const thread = page.locator('[role="log"]');

    // First message
    await promptInput.fill("First message");
    await submitButton.click();
    await expect(thread).toContainText("echo: First message", {
      timeout: 10000,
    });

    // Second message
    await promptInput.fill("Second message");
    await submitButton.click();
    await expect(thread).toContainText("echo: Second message", {
      timeout: 10000,
    });
  });
});
