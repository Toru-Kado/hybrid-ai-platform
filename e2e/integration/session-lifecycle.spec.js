/**
 * Integration test: session lifecycle (CRUD).
 * Verifies creating, renaming, and deleting sessions through the UI.
 */

import { test, expect } from "@playwright/test";

test.describe("Session lifecycle", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector(".chat-layout");
  });

  test("creates a session by sending a message", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("first session message");
    await page.locator('.composer button[type="submit"]').click();

    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("echo:", { timeout: 10000 });

    // Session should appear in sidebar
    const sidebar = page.locator("aside.sidebar");
    await expect(sidebar.locator(".session-item")).toHaveCount(1, {
      timeout: 5000,
    });
    await expect(sidebar).toContainText("first session message");
  });

  test("creates a new session via New chat button", async ({ page }) => {
    const promptInput = page.locator("#prompt");

    // Create first session
    await promptInput.fill("initial session");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText("echo:", {
      timeout: 10000,
    });

    // Click "New chat" button
    await page.locator("aside.sidebar").getByText("New chat").click();

    // Send a message in the new session
    await promptInput.fill("second session message");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText(
      "echo: second session message",
      { timeout: 10000 }
    );

    // Both sessions should be in sidebar
    const sidebar = page.locator("aside.sidebar");
    await expect(sidebar.locator(".session-item")).toHaveCount(2, {
      timeout: 5000,
    });
  });

  test("renames a session", async ({ page }) => {
    const promptInput = page.locator("#prompt");
    await promptInput.fill("rename me");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText("echo:", {
      timeout: 10000,
    });

    // Click "Rename session" button
    await page.getByText("Rename session").click();

    // Fill in new title
    const titleInput = page.locator('input[aria-label="Session title"]');
    await titleInput.clear();
    await titleInput.fill("My Renamed Session");

    // Submit rename
    await page.locator("form.session-title-form").getByText("Save").click();

    // Verify the title updated in sidebar
    const sidebar = page.locator("aside.sidebar");
    await expect(sidebar).toContainText("My Renamed Session", {
      timeout: 5000,
    });
  });

  test("deletes a session", async ({ page }) => {
    const sidebar = page.locator("aside.sidebar");
    const promptInput = page.locator("#prompt");

    // Send a message to create a session
    await promptInput.fill("deletable session xyz");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText("echo:", {
      timeout: 10000,
    });

    // Verify the session with our unique text is in the sidebar
    await expect(
      sidebar.locator(".session-item").filter({ hasText: "deletable session" })
    ).toHaveCount(1, { timeout: 5000 });

    // Handle the confirm dialog
    page.on("dialog", (dialog) => dialog.accept());

    // Delete the session
    await page.getByText("Delete session").click();

    // The specific session should no longer appear
    await expect(
      sidebar.locator(".session-item").filter({ hasText: "deletable session" })
    ).toHaveCount(0, { timeout: 5000 });
  });

  test("navigates between sessions", async ({ page }) => {
    const promptInput = page.locator("#prompt");

    // Create first session
    await promptInput.fill("session one content");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText(
      "echo: session one content",
      { timeout: 10000 }
    );

    // Create second session
    await page.locator("aside.sidebar").getByText("New chat").click();
    await promptInput.fill("session two content");
    await page.locator('.composer button[type="submit"]').click();
    await expect(page.locator('[role="log"]')).toContainText(
      "echo: session two content",
      { timeout: 10000 }
    );

    // Navigate back to first session
    const sidebar = page.locator("aside.sidebar");
    await sidebar
      .locator(".session-item")
      .filter({ hasText: "session one" })
      .click();

    // Verify first session's messages are displayed
    const thread = page.locator('[role="log"]');
    await expect(thread).toContainText("session one content", {
      timeout: 5000,
    });
  });
});
