import { expect, type Page } from "playwright/test";

export const addLegacyComponents = async (page: Page) => {
  await page.getByTestId("sidebar-options-trigger").click();
  await page.getByTestId("sidebar-legacy-switch").isVisible({ timeout: 5000 });
  await page.getByTestId("sidebar-legacy-switch").click();
  await expect(page.getByTestId("sidebar-legacy-switch")).toBeChecked();
  await page.getByTestId("sidebar-options-trigger").click();
};
