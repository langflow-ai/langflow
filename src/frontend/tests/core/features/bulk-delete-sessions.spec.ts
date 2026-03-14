import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import type { Page } from "@playwright/test";

test.describe("Bulk Delete Sessions", () => {
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
    await page.waitForSelector('[data-testid="button-send"][title="Send"]', {
      timeout: 60000,
    });
  }

  // Helper to create a new session with a message
  async function createSessionWithMessage(page: Page, message: string) {
    await page.getByTestId("new-chat").click();
    await page.waitForTimeout(500);
    await sendMessage(page, message);
    await waitForBuildComplete(page, 1);
  }

  // Helper to get session count
  async function getSessionCount(page: Page): Promise<number> {
    const sessions = await page.getByTestId("session-selector").all();
    return sessions.length;
  }

  // Helper to intercept API calls
  async function setupApiInterceptor(page: Page) {
    const apiCalls: string[] = [];

    await page.route("**/api/v1/monitor/messages/sessions*", (route) => {
      const method = route.request().method();
      const url = route.request().url();
      apiCalls.push(`${method} ${url}`);
      route.continue();
    });

    return apiCalls;
  }

  test(
    "should show Select All checkbox when multiple sessions exist",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "First session message");
      await waitForBuildComplete(page, 1);

      // Create second session
      await createSessionWithMessage(page, "Second session message");

      // Verify Select All checkbox is visible
      await expect(page.getByTestId("select-all-checkbox")).toBeVisible();
    },
  );

  test(
    "should select all sessions when Select All checkbox is clicked",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "First session");
      await waitForBuildComplete(page, 1);

      // Create two more sessions
      await createSessionWithMessage(page, "Second session");
      await createSessionWithMessage(page, "Third session");

      // Click Select All checkbox
      await page.getByTestId("select-all-checkbox").click();
      await page.waitForTimeout(500);

      // Verify all session checkboxes are checked (by checking for SquareCheck icon)
      const sessionCheckboxes = await page
        .locator('[data-testid^="session-"][data-testid$="-checkbox"]')
        .all();

      for (const checkbox of sessionCheckboxes) {
        const icon = checkbox.locator("svg");
        await expect(icon).toHaveAttribute("data-testid", "icon-SquareCheck");
      }

      // Verify bulk delete button is visible
      await expect(page.getByTestId("bulk-delete-button")).toBeVisible();
    },
  );

  test(
    "should deselect all sessions when Select All is clicked again",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "First session");
      await waitForBuildComplete(page, 1);

      // Create second session
      await createSessionWithMessage(page, "Second session");

      // Click Select All checkbox twice
      await page.getByTestId("select-all-checkbox").click();
      await page.waitForTimeout(500);
      await page.getByTestId("select-all-checkbox").click();
      await page.waitForTimeout(500);

      // Verify all session checkboxes are unchecked (by checking for Square icon)
      const sessionCheckboxes = await page
        .locator('[data-testid^="session-"][data-testid$="-checkbox"]')
        .all();

      for (const checkbox of sessionCheckboxes) {
        const icon = checkbox.locator("svg");
        await expect(icon).toHaveAttribute("data-testid", "icon-Square");
      }

      // Verify bulk delete button is not visible
      await expect(page.getByTestId("bulk-delete-button")).not.toBeVisible();
    },
  );

  test(
    "should allow individual session selection",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "Default session");
      await waitForBuildComplete(page, 1);

      // Create three more sessions (so we have 3 with checkboxes)
      await createSessionWithMessage(page, "Second session");
      await createSessionWithMessage(page, "Third session");
      await createSessionWithMessage(page, "Fourth session");

      // Select only the first two non-default sessions
      const sessionCheckboxes = await page
        .locator('[data-testid^="session-"][data-testid$="-checkbox"]')
        .all();

      // Verify we have 3 checkboxes (for the 3 non-default sessions)
      expect(sessionCheckboxes.length).toBe(3);

      await sessionCheckboxes[0].click();
      await page.waitForTimeout(300);
      await sessionCheckboxes[1].click();
      await page.waitForTimeout(300);

      // Verify only first two are checked (by checking icon state)
      const icon0 = sessionCheckboxes[0].locator("svg");
      const icon1 = sessionCheckboxes[1].locator("svg");
      const icon2 = sessionCheckboxes[2].locator("svg");
      await expect(icon0).toHaveAttribute("data-testid", "icon-SquareCheck");
      await expect(icon1).toHaveAttribute("data-testid", "icon-SquareCheck");
      await expect(icon2).toHaveAttribute("data-testid", "icon-Square");

      // Verify bulk delete button is visible
      await expect(page.getByTestId("bulk-delete-button")).toBeVisible();
    },
  );

  test(
    "should use bulk delete API endpoint for multiple sessions",
    { tag: ["@release", "@features", "@api"] },
    async ({ page }) => {
      test.skip(
        !process?.env?.OPENAI_API_KEY,
        "OPENAI_API_KEY required to run this test",
      );

      await awaitBootstrapTest(page);

      // Setup API interceptor
      const apiCalls = await setupApiInterceptor(page);

      // Load a starter project
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();
      await initialGPTsetup(page);

      // Open playground
      await page
        .getByRole("button", { name: "Playground", exact: true })
        .click();
      await page.waitForTimeout(2000);

      // Send message in default session
      await sendMessage(page, "First session");
      await waitForBuildComplete(page, 1);

      // Create two more sessions
      await createSessionWithMessage(page, "Second session");
      await createSessionWithMessage(page, "Third session");

      // Get initial session count
      const initialCount = await getSessionCount(page);

      // Clear API calls array
      apiCalls.length = 0;

      // Select all sessions
      await page.getByTestId("select-all-checkbox").click();
      await page.waitForTimeout(500);

      // Click bulk delete button
      await page.getByTestId("bulk-delete-button").click();
      await page.waitForTimeout(2000);

      // Verify only ONE DELETE call was made to the bulk endpoint
      const deleteCalls = apiCalls.filter(
        (call) => call.startsWith("DELETE") && call.includes("/sessions"),
      );
      expect(deleteCalls.length).toBe(1);

      // Verify sessions were deleted
      const finalCount = await getSessionCount(page);
      expect(finalCount).toBeLessThan(initialCount);
    },
  );

  test(
    "should delete all sessions including current and create new default session",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "First session");
      await waitForBuildComplete(page, 1);

      // Create second session
      await createSessionWithMessage(page, "Second session");

      // Select all sessions (only non-default sessions have checkboxes)
      await page.getByTestId("select-all-checkbox").click();
      await page.waitForTimeout(500);

      // Click bulk delete button
      await page.getByTestId("bulk-delete-button").click();
      await page.waitForTimeout(2000);

      // Verify we're still in the default session (it wasn't deleted)
      await expect(page.getByTitle("Default Session")).toBeVisible({
        timeout: 10000,
      });

      // Verify the default session message is still visible (it wasn't deleted)
      await expect(
        page.getByText("First session", { exact: false }).first(),
      ).toBeVisible({ timeout: 5000 });

      // Verify the second session message is not visible (it was deleted)
      await expect(
        page.getByText("Second session", { exact: false }).first(),
      ).not.toBeVisible({ timeout: 5000 });

      // Verify we can send a new message in the new session
      await sendMessage(page, "New session message");
      await waitForBuildComplete(page, 1);
      await expect(
        page.getByText("New session message", { exact: false }).first(),
      ).toBeVisible({ timeout: 10000 });
    },
  );

  test(
    "should hide checkboxes and Select All when only one session exists",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "Only session");
      await waitForBuildComplete(page, 1);

      // Verify Select All checkbox is not visible
      await expect(page.getByTestId("select-all-checkbox")).not.toBeVisible();

      // Verify session checkboxes are not visible
      const sessionCheckboxes = await page
        .locator('[data-testid^="session-"][data-testid$="-checkbox"]')
        .all();
      expect(sessionCheckboxes.length).toBe(0);
    },
  );

  test(
    "should update Select All checkbox state based on individual selections",
    { tag: ["@release", "@features"] },
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

      // Send message in default session
      await sendMessage(page, "First session");
      await waitForBuildComplete(page, 1);

      // Create two more sessions
      await createSessionWithMessage(page, "Second session");
      await createSessionWithMessage(page, "Third session");

      // Get all session checkboxes
      const sessionCheckboxes = await page
        .locator('[data-testid^="session-"][data-testid$="-checkbox"]')
        .all();

      // Select all sessions individually
      for (const checkbox of sessionCheckboxes) {
        await checkbox.click();
        await page.waitForTimeout(200);
      }

      // Verify Select All checkbox is now checked (by checking icon state)
      const selectAllIcon = page
        .getByTestId("select-all-checkbox")
        .locator("svg");
      await expect(selectAllIcon).toHaveAttribute(
        "data-testid",
        "icon-SquareCheck",
      );

      // Uncheck one session
      await sessionCheckboxes[0].click();
      await page.waitForTimeout(300);

      // Verify Select All checkbox is now unchecked (by checking icon state)
      const selectAllIconAfter = page
        .getByTestId("select-all-checkbox")
        .locator("svg");
      await expect(selectAllIconAfter).toHaveAttribute(
        "data-testid",
        "icon-Square",
      );
    },
  );
});
