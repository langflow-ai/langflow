import { Page } from "@playwright/test";

export async function zoomOut(page: Page, times: number = 4) {
  for (let i = 0; i < times; i++) {
    await page.getByTestId("zoom_out").click();
  }
}
