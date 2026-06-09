import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

/**
 * Helper: create Basic Prompting flow, configure GPT, publish,
 * and open the shareable playground in a new tab.
 */
async function setupShareablePlayground(page: any, context: any): Promise<any> {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await initialGPTsetup(page);

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 120000 });

  await page.getByTestId("publish-button").click();
  await page.waitForSelector('[data-testid="shareable-playground"]', {
    timeout: 10000,
  });
  await page.waitForTimeout(1000);
  await page.getByTestId("publish-switch").click();
  await page.waitForTimeout(2000);

  const pagePromise = context.waitForEvent("page");
  await page.getByTestId("shareable-playground").click();
  const newPage = await pagePromise;
  await newPage.waitForTimeout(3000);

  return newPage;
}

/**
 * Helper: send message and wait for build to complete.
 * Uses the same pattern as publish-flow.spec.ts (Stop button lifecycle).
 */
async function sendAndWaitForResponse(playgroundPage: any, message: string) {
  await playgroundPage.getByPlaceholder("Send a message...").fill(message);
  await playgroundPage.getByTestId("button-send").last().click();

  // Wait for Stop button to appear (build started)
  const stopButton = playgroundPage.getByRole("button", { name: "Stop" });
  await stopButton.waitFor({ state: "visible", timeout: 30000 });

  // Wait for Stop button to disappear (build complete)
  await stopButton.waitFor({ state: "hidden", timeout: 120000 });
}

test(
  "shareable playground: auto-login user can send message and get response",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    const playgroundPage = await setupShareablePlayground(page, context);

    await sendAndWaitForResponse(playgroundPage, "Say hello");

    // After build complete, at least one chat message should be visible
    await expect(
      playgroundPage.locator('[data-testid="div-chat-message"]').first(),
    ).toBeVisible({ timeout: 10000 });

    await playgroundPage.close();
  },
);

test(
  "shareable playground: streaming works",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    const playgroundPage = await setupShareablePlayground(page, context);

    await playgroundPage
      .getByPlaceholder("Send a message...")
      .fill("Tell me a short joke");
    await playgroundPage.getByTestId("button-send").last().click();

    // Stop button should appear during build (streaming active)
    await playgroundPage.waitForSelector('[data-testid="button-stop"]', {
      timeout: 30000,
    });

    // Wait for stop button to disappear (streaming finished)
    await playgroundPage.waitForSelector('[data-testid="button-stop"]', {
      state: "detached",
      timeout: 120000,
    });

    // Send button should be back
    await expect(
      playgroundPage.getByTestId("button-send").last(),
    ).toBeVisible();

    await playgroundPage.close();
  },
);

test(
  "shareable playground: session management works",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    const playgroundPage = await setupShareablePlayground(page, context);

    await sendAndWaitForResponse(playgroundPage, "Session test");

    // Create new session
    await playgroundPage.getByTestId("new-chat").click();
    await playgroundPage.waitForTimeout(2000);

    // New session should be created — at least "Default Session" + new one
    // Check that the new-chat button is still clickable (UI didn't crash)
    await expect(playgroundPage.getByTestId("new-chat")).toBeVisible();

    // Verify at least one session-selector exists
    await expect(
      playgroundPage.getByTestId("session-selector").first(),
    ).toBeVisible({ timeout: 5000 });

    await playgroundPage.close();
  },
);
