import type { Page } from "@playwright/test";

export async function zoomOut(page: Page, times: number = 2) {
  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 3000,
  });

  let zoomOutButton = await page.getByTestId("zoom_out").count();
  if (zoomOutButton === 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
    zoomOutButton = await page.getByTestId("zoom_out").count();
  }
  for (let i = 0; i < times; i++) {
    await page.getByTestId("zoom_out").click();
  }
  if (zoomOutButton > 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
  }
}
