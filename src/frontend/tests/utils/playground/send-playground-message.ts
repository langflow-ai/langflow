import type { Page } from "@playwright/test";
import { TEXTS } from "../../utils/constants/texts";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";
export type SendOpts = {
  /** "canvas" = regular playground panel; "shareable" = published page. */
  surface?: "canvas" | "shareable";
  /** "button" = click button-send; "enter" = press Enter key. */
  sendBy?: "button" | "enter";
};

/**
 * Send a message in the playground and wait for the build to complete.
 *
 * Replaces 7+ inline implementations across the suite (`sendMessage`,
 * `sendMessageAndWait`, `sendAndWaitForResponse`, etc.). The defaults
 * mirror the most lenient set of predecessor timeouts (60s for chat
 * input visibility on Windows CI, 30s for the Stop button to appear,
 * 120s for it to disappear).
 */
export async function sendPlaygroundMessage(
  page: Page,
  message: string,
  opts: SendOpts = {},
): Promise<void> {
  const { surface = "canvas", sendBy = "button" } = opts;

  if (surface === "shareable") {
    await page
      .getByPlaceholder(TEXTS.placeholderSendMessage)
      .waitFor({ state: "visible", timeout: TIMEOUTS.long });
    await page.getByPlaceholder(TEXTS.placeholderSendMessage).fill(message);
  } else {
    await page.waitForSelector(`[data-testid="${TID.inputChatPlayground}"]`, {
      timeout: TIMEOUTS.componentMount,
    });
    await page.getByTestId(TID.inputChatPlayground).last().fill(message);
  }

  if (sendBy === "enter") {
    await page.keyboard.press("Enter");
  } else {
    await page.getByTestId(TID.buttonSend).last().click();
  }

  const stop = page.getByRole("button", { name: TEXTS.stop });
  await stop.waitFor({ state: "visible", timeout: TIMEOUTS.standard });
  await stop.waitFor({ state: "hidden", timeout: TIMEOUTS.buildComplete });
}
