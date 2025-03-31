import { Page } from "playwright/test";

export async function removeOldApiKeys(page: Page) {
  let filledApiKey = await page.getByTestId("remove-icon-badge").count();
  while (filledApiKey > 0) {
    await page.getByTestId("remove-icon-badge").first().click();
    filledApiKey = await page.getByTestId("remove-icon-badge").count();
  }
}
