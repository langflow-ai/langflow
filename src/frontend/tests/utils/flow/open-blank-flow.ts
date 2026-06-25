import { expect, type Page } from "@playwright/test";
import { awaitBootstrapTest } from "../await-bootstrap-test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

async function waitForFlowEditor(page: Page): Promise<void> {
  const sidebarSearchInput = page.getByTestId(TID.sidebarSearchInput);
  if (!(await sidebarSearchInput.isVisible())) {
    const createdFlow = page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();

    const createdFlowVisible = await createdFlow
      .waitFor({ state: "visible", timeout: TIMEOUTS.medium })
      .then(() => true)
      .catch(() => false);

    if (createdFlowVisible) {
      await createdFlow.click();
    }
  }

  await expect(sidebarSearchInput).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

/**
 * Bootstrap the app and open a blank flow.
 *
 * Replaces the 3-line ritual that appears in 50+ spec files:
 *   await awaitBootstrapTest(page);
 *   await page.waitForSelector('[data-testid="blank-flow"]', { timeout: 30000 });
 *   await page.getByTestId("blank-flow").click();
 */
export async function openBlankFlow(page: Page): Promise<void> {
  await awaitBootstrapTest(page);
  await page.waitForSelector(`[data-testid="${TID.blankFlow}"]`, {
    timeout: TIMEOUTS.standard,
  });
  await page.getByTestId(TID.blankFlow).click();
  await expect(page.getByTestId(TID.modalTitle)).toBeHidden({
    timeout: TIMEOUTS.standard,
  });
  await waitForFlowEditor(page);
}
