import { Page } from "playwright/test";

export async function adjustScreenView(
  page: Page,
  {
    numberOfZoomOut = 3,
  }: {
    numberOfZoomOut?: number;
  } = {},
) {
  await page.getByTestId("fit_view").click();

  for (let i = 0; i < numberOfZoomOut; i++) {
    await page.getByTestId("zoom_out").click();
  }
}
