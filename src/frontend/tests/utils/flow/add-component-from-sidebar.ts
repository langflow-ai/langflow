import type { Page } from "@playwright/test";
import { SELECTORS, TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

export type AddComponentOpts = {
  /** Search query typed into the sidebar input. */
  search: string;
  /** Exact `data-testid` of the component row in the sidebar (e.g. `input_outputChat Output`). */
  testId: string;
  /** If provided, the component is dragged to this position on the canvas. */
  position?: { x: number; y: number };
  /** If provided, hover + click the inline add button instead of dragging. */
  hoverAdd?: boolean;
  /**
   * Display name slug for the inline "+" button, when the prefix-stripped
   * row testId doesn't already match it. Example: pass `"chat-output"` to
   * target `add-component-button-chat-output`. Defaults to the slug of the
   * row testId with the leading `<category>_<subcategory>` prefix removed
   * (matches `convertTestName(display_name)` from the production UI).
   */
  addButtonSlug?: string;
};

/**
 * Convert the sidebar row testId (e.g. `input_outputChat Output`) into the
 * slug used by the inline add button (`chat-output`). Mirrors the
 * production `convertTestName(display_name)` helper, but reverse-engineered
 * from the row testId because that is what tests already pass in.
 */
function rowTestIdToAddButtonSlug(testId: string): string {
  // Sidebar rows are emitted as `${category}${display_name}` (no
  // separator). The leading category is always lowercase + may contain
  // underscores; the display name starts with the first uppercase letter
  // or digit. Splitting at that boundary gives us the human-readable
  // display name, which we then run through the same slug rule as the
  // production UI (`convertTestName`).
  const match = testId.match(/^([a-z_]+)([A-Z0-9].*)$/);
  const displayName = match ? match[2] : testId;
  return displayName.replace(/ /g, "-").toLowerCase();
}

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
  { search, testId, position, hoverAdd, addButtonSlug }: AddComponentOpts,
): Promise<void> {
  await page.getByTestId(TID.sidebarSearchInput).click();
  await page.getByTestId(TID.sidebarSearchInput).fill(search);
  await page.waitForSelector(`[data-testid="${testId}"]`, {
    timeout: TIMEOUTS.componentMount,
  });

  if (hoverAdd) {
    const slug = addButtonSlug ?? rowTestIdToAddButtonSlug(testId);
    // Scope the "+" button query to the targeted row — the sidebar can
    // surface the same `add-component-button-<slug>` testid on multiple
    // rows (e.g. `input_outputChat Input` AND `saved_componentsChat Input`
    // both render an `add-component-button-chat-input`), and a top-level
    // `page.getByTestId(...)` then trips Playwright's strict-mode check.
    const row = page.getByTestId(testId);
    await row.hover();
    await row.getByTestId(`add-component-button-${slug}`).click();
    return;
  }

  await page
    .getByTestId(testId)
    .dragTo(page.locator(SELECTORS.reactFlowCanvasXPath), {
      targetPosition: position ?? { x: 200, y: 200 },
    });
}
