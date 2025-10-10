import type { Page } from "playwright/test";

export async function removeOldApiKeys(page: Page) {
  let filledApiKey = await page.getByTestId("remove-icon-badge").count();
  while (filledApiKey > 0) {
    await page
      .getByTestId("remove-icon-badge")
      .nth(filledApiKey - 1)
      .click();
    await page.waitForTimeout(1000);
    filledApiKey = await page.getByTestId("remove-icon-badge").count();
  }
}
