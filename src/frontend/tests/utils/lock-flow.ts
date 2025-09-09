import { expect, type Page } from "@playwright/test";

export async function lockFlow(page: Page) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await page.getByTestId("icon-Lock").isVisible({ timeout: 5000 });
  await page.waitForTimeout(500);

  await page.getByTestId("save-flow-settings").click();
  await expect(page.getByTestId("save-flow-settings")).toBeHidden({
    timeout: 5000,
  });
  //ensure the UI is updated
  await page.getByTestId("icon-Lock").isVisible({ timeout: 5000 });
}

export async function unlockFlow(page: Page) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await page.getByTestId("icon-Lock").isVisible({ timeout: 5000 });
  //ensure the UI is updated
  await page.waitForTimeout(500);
  await page.getByTestId("save-flow-settings").click();
  await expect(page.getByTestId("save-flow-settings")).toBeHidden({
    timeout: 5000,
  });
}
