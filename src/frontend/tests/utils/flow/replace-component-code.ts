import type { Page } from "@playwright/test";
import { TEXTS } from "../../utils/constants/texts";
import { TID } from "../constants/testIds";
/**
 * Replace the code of the currently-selected custom component.
 *
 * Replaces the 5-step ritual that appears in 3+ specs:
 *   1. click code-button-modal
 *   2. click .ace_content
 *   3. ControlOrMeta+A (select all)
 *   4. textarea.fill(code)
 *   5. click "Check & Save"
 *
 * The caller is responsible for selecting the target node first.
 */
export async function replaceComponentCode(
  page: Page,
  code: string,
): Promise<void> {
  await page.getByTestId(TID.codeButtonModal).first().click();
  await page.locator(".ace_content").click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.locator("textarea").fill(code);
  await page.getByText(TEXTS.checkAndSave).last().click();
}
