import type { Page } from "@playwright/test";

export async function zoomOut(page: Page, times: number = 2) {
  const zoomOutButton = await page.getByTestId("zoom_out").count();
  if (zoomOutButton === 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
  }
  for (let i = 0; i < times; i++) {
    await page.getByTestId("zoom_out").click();
  }

  await page.getByTestId("canvas_controls_dropdown").click();
}
