import { expect, type Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

export async function waitForFlowEditorReady(page: Page): Promise<void> {
  await expect(page.getByTestId(TID.modalTitle)).toBeHidden({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.locator("#react-flow-id")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  const sidebarSearchInput = page.getByTestId(TID.sidebarSearchInput);
  if (!(await sidebarSearchInput.isVisible().catch(() => false))) {
    const newSidebarComponentsButton = page.locator(
      '[data-sidebar-collapsed-nav-item="components"]',
    );
    if (await newSidebarComponentsButton.isVisible().catch(() => false)) {
      await newSidebarComponentsButton.click();
    } else {
      await page.locator('[data-sidebar="trigger"]').first().click();
    }
  }
  await expect(sidebarSearchInput).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.getByTestId(TID.flowSidebar)).toHaveAttribute(
    "data-search-hotkey-ready",
    "true",
    { timeout: TIMEOUTS.standard },
  );
  const catalogEntry = page.locator('[data-testid$="_draggable"]').first();
  if (!(await catalogEntry.isVisible().catch(() => false))) {
    const firstCategory = page.locator('[data-testid^="disclosure-"]').first();
    await expect(firstCategory).toBeVisible({ timeout: TIMEOUTS.standard });
    if ((await firstCategory.getAttribute("aria-expanded")) !== "true") {
      await firstCategory.click();
    }
  }
  await expect(catalogEntry).toBeVisible({ timeout: TIMEOUTS.standard });
}
