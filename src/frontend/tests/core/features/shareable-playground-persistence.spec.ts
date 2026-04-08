import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

// These tests require the server to run with AUTO_LOGIN=FALSE.
// When the server runs with AUTO_LOGIN=TRUE (default for local dev),
// the backend uses client_id instead of user_id for session isolation,
// and persistence features are not active.
// Set LANGFLOW_AUTO_LOGIN=false in your .env to run these tests.

/**
 * Helper: mock auto-login as disabled and log in manually.
 */
async function setupAutoLoginOff(page: any) {
  await page.route("**/api/v1/auto_login", (route: any) => {
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: { auto_login: false } }),
    });
  });

  await page.addInitScript(() => {
    window.process = window.process || ({} as any);
    const newEnv = {
      ...(window.process as any).env,
      LANGFLOW_AUTO_LOGIN: "false",
    };
    Object.defineProperty(window.process, "env", {
      value: newEnv,
      writable: true,
      configurable: true,
    });
    sessionStorage.setItem("testMockAutoLogin", "true");
  });

  await page.goto("/");
  await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

  await page.getByPlaceholder("Username").fill("langflow");
  await page.getByPlaceholder("Password").fill("langflow");

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });

  await page.getByRole("button", { name: "Sign In" }).click();

  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });
}

/**
 * Helper: create Basic Prompting flow, configure GPT, publish,
 * and return the shareable playground URL.
 */
async function createPublishAndGetUrl(
  page: any,
  context: any,
): Promise<string> {
  await page.waitForSelector('[id="new-project-btn"]', { timeout: 30000 });

  await awaitBootstrapTest(page, { skipGoto: true });

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await initialGPTsetup(page);

  // Build first
  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 120000 });

  // Publish
  await page.getByTestId("publish-button").click();
  await page.waitForSelector('[data-testid="shareable-playground"]', {
    timeout: 10000,
  });
  await page.waitForTimeout(1000);
  await page.getByTestId("publish-switch").click();
  await page.waitForTimeout(2000);

  // Get URL
  const pagePromise = context.waitForEvent("page");
  await page.getByTestId("shareable-playground").click();
  const newPage = await pagePromise;
  await newPage.waitForTimeout(2000);
  const url = newPage.url();
  await newPage.close();

  return url;
}

/**
 * Helper: send a message and wait for the build to complete.
 */
async function sendMessageAndWait(page: any, message: string) {
  await page.getByPlaceholder("Send a message...").fill(message);
  await page.getByTestId("button-send").last().click();

  // Wait for Stop button lifecycle (build started → completed)
  const stopButton = page.getByRole("button", { name: "Stop" });
  await stopButton.waitFor({ state: "visible", timeout: 30000 });
  await stopButton.waitFor({ state: "hidden", timeout: 120000 });

  await page.waitForTimeout(2000);
}

test(
  "shareable playground: logged-in user messages persist after page refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      process?.env?.LANGFLOW_AUTO_LOGIN !== "false",
      "Server must run with AUTO_LOGIN=FALSE for persistence tests",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await setupAutoLoginOff(page);
    const playgroundUrl = await createPublishAndGetUrl(page, context);

    // Navigate to shareable playground
    await page.goto(playgroundUrl);
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });

    // Send message
    await sendMessageAndWait(page, "persist test");

    // Should have messages
    const messagesBefore = await page
      .locator('[data-testid="div-chat-message"]')
      .count();
    expect(messagesBefore).toBeGreaterThanOrEqual(2);

    // Refresh
    await page.reload();
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });
    await page.waitForTimeout(3000);

    // Messages should still be visible
    const messagesAfter = await page
      .locator('[data-testid="div-chat-message"]')
      .count();
    expect(messagesAfter).toBeGreaterThanOrEqual(2);
  },
);

test(
  "shareable playground: default session appears first",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      process?.env?.LANGFLOW_AUTO_LOGIN !== "false",
      "Server must run with AUTO_LOGIN=FALSE for persistence tests",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await setupAutoLoginOff(page);
    const playgroundUrl = await createPublishAndGetUrl(page, context);

    await page.goto(playgroundUrl);
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });

    // Send message in default session
    await sendMessageAndWait(page, "default session msg");

    // Create new session
    await page.getByTestId("new-chat").click();
    await page.waitForTimeout(1000);

    // First session should be Default Session
    const firstSession = page.getByTestId("session-selector").first();
    await expect(firstSession).toContainText("Default Session");
  },
);

test(
  "shareable playground: delete session persists after refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      process?.env?.LANGFLOW_AUTO_LOGIN !== "false",
      "Server must run with AUTO_LOGIN=FALSE for persistence tests",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await setupAutoLoginOff(page);
    const playgroundUrl = await createPublishAndGetUrl(page, context);

    await page.goto(playgroundUrl);
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });

    // Send message
    await sendMessageAndWait(page, "keep this");

    // Create new session and send message
    await page.getByTestId("new-chat").click();
    await page.waitForTimeout(1000);
    await sendMessageAndWait(page, "delete this");

    const sessionsBefore = await page.getByTestId("session-selector").count();

    // Delete last session
    await page
      .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
      .last()
      .click();
    await page.getByTestId("delete-session-option").click();
    await page.waitForTimeout(2000);

    const sessionsAfterDelete = await page
      .getByTestId("session-selector")
      .count();
    expect(sessionsAfterDelete).toBeLessThan(sessionsBefore);

    // Refresh
    await page.reload();
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });
    await page.waitForTimeout(3000);

    const sessionsAfterRefresh = await page
      .getByTestId("session-selector")
      .count();
    expect(sessionsAfterRefresh).toBeLessThanOrEqual(sessionsAfterDelete);
  },
);

test(
  "shareable playground: rename session persists after refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      process?.env?.LANGFLOW_AUTO_LOGIN !== "false",
      "Server must run with AUTO_LOGIN=FALSE for persistence tests",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await setupAutoLoginOff(page);
    const playgroundUrl = await createPublishAndGetUrl(page, context);

    await page.goto(playgroundUrl);
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });

    // Create new session and send message
    await page.getByTestId("new-chat").click();
    await page.waitForTimeout(1000);
    await sendMessageAndWait(page, "rename test");

    // Rename session
    await page
      .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
      .last()
      .click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("Custom Name");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(1000);

    await expect(
      page.getByTestId("session-selector").getByText("Custom Name"),
    ).toBeVisible({ timeout: 5000 });

    // Refresh
    await page.reload();
    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 30000,
    });
    await page.waitForTimeout(3000);

    // Renamed session should persist
    await expect(
      page.getByTestId("session-selector").getByText("Custom Name"),
    ).toBeVisible({ timeout: 10000 });
  },
);
