import { expect, type Page } from "@playwright/test";
import { SELECTORS, TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

/** How many times a swallowed drag is re-attempted before failing. */
const DRAG_ATTEMPTS = 3;

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
    const nodes = page.locator(".react-flow__node");
    const slug = addButtonSlug ?? rowTestIdToAddButtonSlug(testId);
    // Scope the "+" button query to the targeted row — the sidebar can
    // surface the same `add-component-button-<slug>` testid on multiple
    // rows (e.g. `input_outputChat Input` AND `saved_componentsChat Input`
    // both render an `add-component-button-chat-input`), and a top-level
    // `page.getByTestId(...)` then trips Playwright's strict-mode check.
    const row = page.getByTestId(testId);
    await row.hover();
    const rowContainer = row.locator("xpath=..");
    await expect(page.getByTestId("canvas-add-note-button")).toBeEnabled({
      timeout: TIMEOUTS.standard,
    });
    const addButton = rowContainer.getByTestId(`add-component-button-${slug}`);
    await expect(addButton).toBeVisible({ timeout: TIMEOUTS.standard });
    const previousNodeCount = await nodes.count();
    await addButton.click();
    await expect(nodes).toHaveCount(previousNodeCount + 1, {
      timeout: TIMEOUTS.standard,
    });
    return;
  }

  const nodes = page.locator(".react-flow__node");
  const previousNodeCount = await nodes.count();
  const canvas = page.locator(SELECTORS.reactFlowCanvasXPath);

  // A drag can be swallowed whole: the HTML5 drag sequence starts on a sidebar
  // row React is still re-rendering after the search (or a legacy-toggle), the
  // drop never reaches the canvas, and no node appears — with no error, so the
  // spec only fails much later on a handle that does not exist. Reproduced on a
  // CPU-starved renderer; it is what cost Windows CI the Text Input node in
  // stop-building.spec.ts. Retry, but only when nothing landed at all, so a
  // slow-but-successful drop is never duplicated into a second node.
  for (let attempt = 1; attempt <= DRAG_ATTEMPTS; attempt++) {
    await page.getByTestId(testId).dragTo(canvas, {
      targetPosition: position ?? { x: 200, y: 200 },
    });
    try {
      await expect(nodes).toHaveCount(previousNodeCount + 1, {
        timeout: TIMEOUTS.standard,
      });
      return;
    } catch (error) {
      const landed = (await nodes.count()) !== previousNodeCount;
      if (attempt === DRAG_ATTEMPTS || landed) {
        throw error;
      }
    }
  }
}
