import { Page } from "playwright/test";

export async function adjustScreenView(page: Page) {
  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
}
