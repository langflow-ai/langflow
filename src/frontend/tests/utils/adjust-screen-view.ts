import type { Page } from "@playwright/test";

export async function adjustScreenView(
  page: Page,
  {
    numberOfZoomOut = 1,
  }: {
    numberOfZoomOut?: number;
  } = {},
) {
  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 30000,
  });

  let fitViewButton = await page.getByTestId("fit_view").count();

  if (fitViewButton === 0) {
    await page.getByTestId("canvas_controls_dropdown").click();
    fitViewButton = await page.getByTestId("fit_view").count();
  }

  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);

  for (let i = 0; i < numberOfZoomOut; i++) {
    const zoomOutButton = page.getByTestId("zoom_out");

    if (await zoomOutButton.isDisabled({ timeout: 1000 })) {
      break;
    }
    // `noWaitAfter` keeps the click from blocking on scheduled navigations.
    // On a busy runner the zoom-out button can be ready while a background
    // route is still in flight, and the default click would then sit there
    // until the 1s timeout fires — turning a successful zoom into a flake.
    await zoomOutButton.click({ timeout: 5000, noWaitAfter: true });
  }
  if (fitViewButton > 0) {
    await page
      .getByTestId("canvas_controls_dropdown")
      .click({ force: true, timeout: 5000, noWaitAfter: true });
  }
}
