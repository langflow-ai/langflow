import { expect, type Page } from "@playwright/test";

export async function lockFlow(page: Page) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await page.getByTestId("icon-Lock").isVisible({ timeout: 5000 });
  const lockSwitch = page.getByTestId("lock-flow-switch");
  await expect(lockSwitch).toBeVisible({ timeout: 1000 });
  await expect(lockSwitch).toHaveAttribute("data-state", "checked");

  await page.waitForTimeout(500);
  await page.getByTestId("save-flow-settings").isEnabled({ timeout: 3000 });
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
  const lockSwitch = page.getByTestId("lock-flow-switch");
  await expect(lockSwitch).toBeVisible({ timeout: 1000 });
  await expect(lockSwitch).toHaveAttribute("data-state", "unchecked");
  //ensure the UI is updated
  await page.waitForTimeout(500);

  await page.getByTestId("save-flow-settings").isEnabled({ timeout: 3000 });
  await page.getByTestId("save-flow-settings").click();
  await expect(page.getByTestId("save-flow-settings")).toBeHidden({
    timeout: 5000,
  });
}
