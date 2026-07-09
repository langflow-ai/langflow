// These tests require the server to run with AUTO_LOGIN=FALSE.
// When the server runs with AUTO_LOGIN=TRUE (default for local dev),
// the backend uses client_id instead of user_id for session isolation,
// and persistence features are not active.
// Set LANGFLOW_AUTO_LOGIN=false in your .env to run these tests.

import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { mockAutoLoginDisabled } from "../../utils/auth/mock-auto-login-disabled";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { publishBasicPromptingAndOpenShareablePlayground } from "../../utils/playground/publish-and-open-shareable";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { sessionMoreMenu } from "../../utils/playground/sessions";

/**
 * Stub auto-login, navigate to the sign-in page, log in manually.
 */
async function setupAutoLoginOff(page: Page): Promise<void> {
  await mockAutoLoginDisabled(page);

  await page.goto("/");
  await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
    timeout: TIMEOUTS.standard,
  });

  await page
    .getByPlaceholder(TEXTS.placeholderUsername)
    .fill(TEXTS.authDefaultCredential);
  await page
    .getByPlaceholder(TEXTS.placeholderPassword)
    .fill(TEXTS.authDefaultPassword);

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });

  await page.getByRole("button", { name: TEXTS.signIn }).click();

  await page.waitForSelector(`[data-testid="${TID.mainpageTitle}"]`, {
    timeout: TIMEOUTS.standard,
  });
}

test(
  "shareable playground: logged-in user messages persist after page refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    skipIfMissing.autoLoginDisabled();
    loadDotenvIfLocal(__dirname);

    await setupAutoLoginOff(page);
    const { url: playgroundUrl, playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context, {
        skipBootstrap: true,
      });
    await playgroundPage.close();

    await page.goto(playgroundUrl);
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    await sendPlaygroundMessage(page, "persist test", {
      surface: "shareable",
    });

    const messagesBefore = await page
      .locator(`[data-testid="${TID.chatMessage}"]`)
      .count();
    expect(messagesBefore).toBeGreaterThanOrEqual(2);

    await page.reload();
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    const messagesAfter = await page
      .locator(`[data-testid="${TID.chatMessage}"]`)
      .count();
    expect(messagesAfter).toBeGreaterThanOrEqual(2);
  },
);

test(
  "shareable playground: default session appears first",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    skipIfMissing.autoLoginDisabled();
    loadDotenvIfLocal(__dirname);

    await setupAutoLoginOff(page);
    const { url: playgroundUrl, playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context, {
        skipBootstrap: true,
      });
    await playgroundPage.close();

    await page.goto(playgroundUrl);
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    await sendPlaygroundMessage(page, "default session msg", {
      surface: "shareable",
    });

    // Create new session
    await page.getByTestId(TID.newChat).click();

    // First session should be Default Session
    const firstSession = page.getByTestId(TID.sessionSelector).first();
    await expect(firstSession).toContainText("Default Session");
  },
);

test(
  "shareable playground: delete session persists after refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    skipIfMissing.autoLoginDisabled();
    loadDotenvIfLocal(__dirname);

    await setupAutoLoginOff(page);
    const { url: playgroundUrl, playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context, {
        skipBootstrap: true,
      });
    await playgroundPage.close();

    await page.goto(playgroundUrl);
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    await sendPlaygroundMessage(page, "keep this", { surface: "shareable" });

    // Create new session and send a message in it
    await page.getByTestId(TID.newChat).click();
    await sendPlaygroundMessage(page, "delete this", { surface: "shareable" });

    const sessionsBefore = await page.getByTestId(TID.sessionSelector).count();

    // Delete last session
    await sessionMoreMenu(page, "last").click();
    await page.getByTestId("delete-session-option").click();

    const sessionsAfterDelete = await page
      .getByTestId(TID.sessionSelector)
      .count();
    expect(sessionsAfterDelete).toBeLessThan(sessionsBefore);

    // Refresh
    await page.reload();
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    const sessionsAfterRefresh = await page
      .getByTestId(TID.sessionSelector)
      .count();
    expect(sessionsAfterRefresh).toBeLessThanOrEqual(sessionsAfterDelete);
  },
);

test(
  "shareable playground: rename session persists after refresh",
  { tag: ["@release", "@api", "@database"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    skipIfMissing.autoLoginDisabled();
    loadDotenvIfLocal(__dirname);

    await setupAutoLoginOff(page);
    const { url: playgroundUrl, playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context, {
        skipBootstrap: true,
      });
    await playgroundPage.close();

    await page.goto(playgroundUrl);
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    // Create new session and send message
    await page.getByTestId(TID.newChat).click();
    await sendPlaygroundMessage(page, "rename test", { surface: "shareable" });

    // Rename session
    await sessionMoreMenu(page, "last").click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("Custom Name");
    await page.keyboard.press("Enter");

    await expect(
      page.getByTestId(TID.sessionSelector).getByText("Custom Name"),
    ).toBeVisible({ timeout: TIMEOUTS.medium });

    // Refresh
    await page.reload();
    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.standard,
    });

    // Renamed session should persist
    await expect(
      page.getByTestId(TID.sessionSelector).getByText("Custom Name"),
    ).toBeVisible({ timeout: TIMEOUTS.medium });
  },
);
