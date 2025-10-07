import type { Page } from "playwright/test";

export async function adjustScreenView(
  page: Page,
  {
    numberOfZoomOut = 1,
  }: {
    numberOfZoomOut?: number;
  } = {},
) {
  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 5000,
  });

  let fitViewButton = await page.getByTestId("fit_view").count();

  if (fitViewButton === 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
    fitViewButton = await page.getByTestId("fit_view").count();
  }

  await page.getByTestId("fit_view").click();

  for (let i = 0; i < numberOfZoomOut; i++) {
    const zoomOutButton = page.getByTestId("zoom_out");

    if (await zoomOutButton.isDisabled()) {
      break;
    } else {
      await zoomOutButton.click();
    }
  }
  if (fitViewButton > 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
  }
}
