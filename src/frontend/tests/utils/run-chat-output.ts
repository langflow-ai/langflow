import type { Page } from "@playwright/test";

export async function runChatOutput(page: Page) {
  try {
    await page.getByTestId("button_run_chat output").click({
      timeout: 1000,
    });
  } catch (error) {
    await page.getByTestId("generic-node-title-arrangement").last().click();
    await page.getByTestId("more-options-modal").last().click();
    await page.getByTestId("expand-button-modal").last().click();
    await page.getByTestId("button_run_chat output").click();
  }
}
