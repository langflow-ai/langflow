import type { Page } from "@playwright/test";

export const unselectNodes = async (page: Page) => {
    await page.locator(".react-flow__pane").click();
    await page.waitForTimeout(500);
}