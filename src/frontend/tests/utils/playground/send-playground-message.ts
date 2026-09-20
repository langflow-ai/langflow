import { expect, type Page } from "@playwright/test";
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
 * input visibility on Windows CI, 30s for the build to show up, 120s
 * for it to finish).
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

  const stop = page.getByRole("button", { name: TEXTS.stop });
  const messages = page.getByTestId(TID.chatMessage);
  // Counted after the transcript is on screen so a still-loading history is not
  // mistaken for the answer to this message.
  const messagesBefore = await messages.count();

  if (sendBy === "enter") {
    await page.keyboard.press("Enter");
  } else {
    await page.getByTestId(TID.buttonSend).last().click();
  }

  // Stop is the Send button under a different accessible name, so it only
  // exists while `isBuilding` is true. A trivial flow answers in ~100ms, which
  // a slow runner can consume between the keypress and Playwright's first poll
  // — the Windows CI shards timed out here on builds that had already finished
  // and rendered their answer. Never having seen Stop is therefore not a
  // failure; accept a new message in the transcript as the same evidence.
  await expect
    .poll(
      async () =>
        (await stop.count()) > 0 || (await messages.count()) > messagesBefore,
      {
        timeout: TIMEOUTS.standard,
        message: "build neither started nor produced a message",
      },
    )
    .toBe(true);
  await stop.waitFor({ state: "hidden", timeout: TIMEOUTS.buildComplete });
}
