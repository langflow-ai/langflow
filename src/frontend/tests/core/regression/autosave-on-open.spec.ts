import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * Opening a flow used to write it: the model-input refresh and the mount
 * template refresh both reached the same autosave trigger as a real edit, so
 * looking at a flow saved it (#8995).
 *
 * The unit tests cover the store gate and each hook on its own. Only this
 * covers the wiring between them — passing `handleNodeClass` where
 * `applyNodeClassFromRefresh` belongs brings the bug back with every unit test
 * still green.
 */

// Both tests bootstrap a flow of their own, and two of those landing at once
// makes the shared creation step return 400.
test.describe.configure({ mode: "serial" });

const IDLE_WINDOW_MS = 12_000;
const SAVE_WINDOW_MS = 9_000;

function trackFlowWrites(page: Page): { count: () => number } {
  let count = 0;
  page.on("request", (request) => {
    if (
      request.method() === "PATCH" &&
      /\/api\/v\d\/flows\/[0-9a-f-]{36}/i.test(request.url())
    ) {
      count += 1;
    }
  });
  return { count: () => count };
}

test(
  "opening a flow does not save it",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const writes = trackFlowWrites(page);

    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(IDLE_WINDOW_MS);

    expect(
      writes.count(),
      "a flow nobody touched must not be written back",
    ).toBe(0);
  },
);

test(
  "an edit is still saved after the open no longer saves",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(IDLE_WINDOW_MS);

    const writes = trackFlowWrites(page);
    const node = page
      .locator('.react-flow__node[data-id^="ChatInput"]')
      .first();
    await expect(node).toBeVisible();
    const box = await node.boundingBox();
    if (!box) throw new Error("the Chat Input node has no bounding box");

    const before = box.y;
    await page.mouse.move(box.x + box.width / 2, box.y + 10);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, box.y + 190, { steps: 14 });
    await page.mouse.up();

    await expect
      .poll(() => writes.count(), { timeout: SAVE_WINDOW_MS })
      .toBeGreaterThan(0);

    // The save is only proven by the reload: a request that never reached the
    // database would still have satisfied the assertion above.
    await page.reload();
    await page.waitForSelector(".react-flow__node", { timeout: 30_000 });
    await adjustScreenView(page);
    const reloaded = await page
      .locator('.react-flow__node[data-id^="ChatInput"]')
      .first()
      .boundingBox();
    if (!reloaded) throw new Error("the Chat Input node did not come back");

    expect(
      Math.abs(reloaded.y - before),
      "the moved node must come back where it was left",
    ).toBeGreaterThan(20);
  },
);
