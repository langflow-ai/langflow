import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test.describe("Session Deletion Data Leakage Fix", () => {
  // Helper to send a message in the playground
  async function sendMessage(page: Page, message: string) {
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 10000,
    });
    await page.getByTestId("input-chat-playground").last().fill(message);
    await page.getByTestId("button-send").last().click();
  }

  // Helper to wait for the flow build to complete after sending a message
  async function waitForBuildComplete(
    page: Page,
    expectedBotMessageCount: number,
  ) {
    // Wait until the expected number of bot messages appear
    await page.waitForFunction(
      (count) =>
        document.querySelectorAll('[data-testid="div-chat-message"]').length >=
        count,
      expectedBotMessageCount,
      { timeout: 60000 },
    );
    // Wait for the build to actually finish by checking the button title
    // The button title changes from "Cancel" to "Send" when isBuilding becomes false
    // Note: button-send is never disabled during builds (disabled is for file uploads only)
    await page.waitForSelector('[data-testid="button-send"][title="Send"]', {
      timeout: 60000,
    });
  }

  // Helper to delete a session via the more menu
  async function deleteSession(page: Page, sessionName: string) {
    // Find all session selectors
    const sessionSelectors = await page.getByTestId("session-selector").all();

    // Find the one with exact matching text
    for (const selector of sessionSelectors) {
      const text = await selector.textContent();
      // Use exact match to avoid matching "Default Session" when looking for "New Session 0"
      if (text?.trim() === sessionName) {
        // Hover to make the more button visible
        await selector.hover();
        await page.waitForTimeout(500); // Wait for hover effects

        // Click the more options button
        const moreButton = selector.locator('[aria-label="More options"]');
        await moreButton.click({ timeout: 5000 });

        // Wait for the menu to open
        await page.waitForTimeout(500);

        // Wait for delete option to be visible and click it
        await page
          .getByTestId("delete-session-option")
          .waitFor({ state: "visible", timeout: 5000 });
        await page.getByTestId("delete-session-option").click();
        await page.waitForTimeout(1000);
        break;
      }
    }
  }

  // Helper to get message count in the current view
  async function getMessageCount(page: Page): Promise<number> {
    const messages = await page
      .locator('[data-testid="div-chat-message"]')
      .all();
    return messages.length;
  }

  test(
    "should prevent data leakage when default session is deleted and recreated",
    { tag: ["@release", "@regression"] },
    async ({ page }) => {
      test.skip(
        !process?.env?.OPENAI_API_KEY,
        "OPENAI_API_KEY required to run this test",
      );

      await awaitBootstrapTest(page);

      // Load a starter project
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();
      await initialGPTsetup(page);

      // Open playground
      await page
        .getByRole("button", { name: "Playground", exact: true })
        .click();
      await page.waitForTimeout(2000);

      // Send message in default session and wait for build to complete
      const originalMessage = `Original message ${Date.now()}`;
      await sendMessage(page, originalMessage);
      await waitForBuildComplete(page, 1);

      // Verify message appears (auto-retry until visible)
      await expect(
        page.getByText(originalMessage, { exact: false }).first(),
      ).toBeVisible({ timeout: 10000 });

      // Delete the default session
      await deleteSession(page, "Default Session");

      // Wait for old messages to be cleared from the DOM
      await page.waitForFunction(
        () =>
          document.querySelectorAll('[data-testid="div-chat-message"]')
            .length === 0,
        { timeout: 10000 },
      );

      // Verify the old message does NOT appear after deletion
      await expect(
        page.getByText(originalMessage, { exact: false }).first(),
      ).not.toBeVisible({ timeout: 10000 });

      // Send a different message (this will be in a new/recreated default session)
      const newMessage = `New message ${Date.now()}`;
      await sendMessage(page, newMessage);
      await waitForBuildComplete(page, 1);

      // Verify only the new message appears
      await expect(
        page.getByText(newMessage, { exact: false }).first(),
      ).toBeVisible({ timeout: 10000 });
      await expect(
        page.getByText(originalMessage, { exact: false }).first(),
      ).not.toBeVisible({ timeout: 10000 });

      // Verify message count is correct (should only have the new message)
      const messageCount = await getMessageCount(page);
      expect(messageCount).toBe(1);
    },
  );

  test(
    "should clear LLM context when session is deleted",
    { tag: ["@release", "@regression"] },
    async ({ page }) => {
      test.skip(
        !process?.env?.OPENAI_API_KEY,
        "OPENAI_API_KEY required to run this test",
      );

      await awaitBootstrapTest(page);

      // Load a starter project with memory
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();
      await initialGPTsetup(page);

      // Open playground
      await page
        .getByRole("button", { name: "Playground", exact: true })
        .click();
      await page.waitForTimeout(2000);

      // Send a message with specific information in default session
      await sendMessage(page, "My name is Victor");
      await waitForBuildComplete(page, 1);

      // Delete the default session to clear context
      await deleteSession(page, "Default Session");

      // Wait for old messages to be cleared
      await page.waitForFunction(
        () =>
          document.querySelectorAll('[data-testid="div-chat-message"]')
            .length === 0,
        { timeout: 10000 },
      );

      // Ask a question that would require the deleted context
      await sendMessage(page, "What is my name?");
      await waitForBuildComplete(page, 1);

      // Get the response text from the last bot message
      const messages = await page
        .locator('[data-testid="div-chat-message"]')
        .all();
      const lastMessage = messages[messages.length - 1];
      const responseText = await lastMessage.textContent();

      // Verify the AI does NOT remember "Victor" from the deleted session
      // The response should indicate it doesn't know the name
      expect(responseText?.toLowerCase()).not.toContain("victor");
    },
  );
});
