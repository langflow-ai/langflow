import type { Page } from "@playwright/test";
import { SELECTORS, TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

export type AddComponentOpts = {
  /** Search query typed into the sidebar input. */
  search: string;
  /** Exact `data-testid` of the component row in the sidebar. */
  testId: string;
  /** If provided, the component is dragged to this position on the canvas. */
  position?: { x: number; y: number };
  /** If provided, hover + click the inline add button instead of dragging. */
  hoverAdd?: boolean;
};

/**
 * Search the sidebar and add a component to the canvas.
 *
 * Replaces the 5-line ritual that appears 60+ times across the suite:
 *   await page.getByTestId("sidebar-search-input").click();
 *   await page.getByTestId("sidebar-search-input").fill("<search>");
 *   await page.waitForSelector('[data-testid="<id>"]', { timeout: 100000 });
 *   await page.getByTestId("<id>").dragTo(<react flow canvas>, { ... });
 *
 * Pass `position` to drag; pass `hoverAdd` to use the inline + button.
 */
export async function addComponentFromSidebar(
  page: Page,
  { search, testId, position, hoverAdd }: AddComponentOpts,
): Promise<void> {
  await page.getByTestId(TID.sidebarSearchInput).click();
  await page.getByTestId(TID.sidebarSearchInput).fill(search);
  await page.waitForSelector(`[data-testid="${testId}"]`, {
    timeout: TIMEOUTS.componentMount,
  });

  if (hoverAdd) {
    await page.getByTestId(testId).hover();
    await page
      .getByTestId(`add-component-button-${testId.toLowerCase()}`)
      .click();
    return;
  }

  await page
    .getByTestId(testId)
    .dragTo(page.locator(SELECTORS.reactFlowCanvasXPath), {
      targetPosition: position ?? { x: 200, y: 200 },
    });
}
