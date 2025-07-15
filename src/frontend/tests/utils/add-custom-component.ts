import type { Page } from "playwright/test";

export const addCustomComponent = async (page: Page) => {
  let numberOfCustomComponents = 0;

  while (numberOfCustomComponents === 0) {
    await page.getByTestId("sidebar-custom-component-button").click();
    numberOfCustomComponents = await page
      .locator('[data-testid="title-Custom Component"]')
      .count();
  }
};
