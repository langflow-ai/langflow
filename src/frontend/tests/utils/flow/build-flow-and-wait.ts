import type { Page } from "@playwright/test";
import { TEXTS } from "../../utils/constants/texts";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";
/**
 * Click the Run button on the Chat Output and wait for "built successfully".
 *
 * Replaces the 2-line build ritual that appears in 17+ specs.
 */
export async function buildFlowAndWait(
  page: Page,
  options?: { timeoutMs?: number },
): Promise<void> {
  await page.getByTestId(TID.buttonRunChatOutput).click();
  await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
    timeout: options?.timeoutMs ?? TIMEOUTS.buildComplete,
  });
}
