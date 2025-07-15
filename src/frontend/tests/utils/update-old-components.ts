import type { Page } from "playwright/test";

export async function updateOldComponents(page: Page) {
  const hasUpdateAllButton = await page
    .getByTestId("update-all-button")
    .count();
  if (hasUpdateAllButton === 0) {
    return;
  }
  await page.getByTestId("update-all-button").click();
  await page.waitForSelector("text=successfully updated", { timeout: 10000 });
}
