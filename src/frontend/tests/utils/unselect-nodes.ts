import type { Page } from "@playwright/test";

export const unselectNodes = async (page: Page) => {
  await page.locator(".react-flow__pane").click({ position: { x: 0, y: 0 } });
  await page.waitForTimeout(500);
};
