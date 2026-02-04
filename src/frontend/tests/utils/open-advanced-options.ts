import type { Page } from "@playwright/test";

export const openAdvancedOptions = async (page: Page) => {
  if ((await page.getByTestId("edit-button-modal").count()) > 0) {
    await page.getByTestId("edit-button-modal").click();
  } else {
    await page.getByTestId("edit-fields-button").click();
  }
};

export const closeAdvancedOptions = async (page: Page) => {
  if ((await page.getByTestId("edit-button-close").count()) > 0) {
    await page.getByTestId("edit-button-close").click();
  } else {
    await page.getByTestId("edit-fields-button").click();
  }
};
