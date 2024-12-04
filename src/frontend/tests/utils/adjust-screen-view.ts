import { Page } from "playwright/test";

export async function adjustScreenView(page: Page) {
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
}
