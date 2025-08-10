import type { Page } from "playwright/test";

export async function adjustScreenView(
  page: Page,
  {
    numberOfZoomOut = 1,
  }: {
    numberOfZoomOut?: number;
  } = {},
) {
  await page.getByTestId("fit_view").click();

  for (let i = 0; i < numberOfZoomOut; i++) {
    const zoomOutButton = page.getByTestId("zoom_out");

    if (await zoomOutButton.isDisabled()) {
      break;
    } else {
      await zoomOutButton.click();
    }
  }
}
