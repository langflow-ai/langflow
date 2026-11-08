import type { Page, Response } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * Memories and Traces replace the canvas. An autosave that lands while one of
 * them is open must still hand its new version token to the editor, or the next
 * save is refused as a conflict with the user's own saved edit.
 */

test.describe.configure({ mode: "serial" });

const SETTLE_MS = 12_000;
const SAVE_WINDOW_MS = 20_000;

const isFlowWrite = (response: Response) =>
  response.request().method() === "PATCH" &&
  /\/api\/v\d\/flows\/[0-9a-f-]{36}/i.test(response.url());

async function dragFirstNode(page: Page): Promise<void> {
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();
  const box = await node.boundingBox();
  if (!box) throw new Error("the node has no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 170, { steps: 14 });
  await page.mouse.up();
}

for (const section of ["memories", "traces"]) {
  test(
    `an autosave that lands while ${section} is open keeps autosave working`,
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openStarterProject(page, "Basic Prompting");
      await adjustScreenView(page);
      await page.waitForTimeout(SETTLE_MS);

      const statuses: number[] = [];
      page.on("response", (response) => {
        if (isFlowWrite(response)) statuses.push(response.status());
      });

      // Hold the first save's response until the canvas is gone, so it lands
      // while Memories or Traces is open however fast the server answers.
      let releaseResponse = () => {};
      const canvasGone = new Promise<void>((resolve) => {
        releaseResponse = resolve;
      });
      let held = false;
      await page.route(/\/api\/v\d\/flows\/[0-9a-f-]{36}/i, async (route) => {
        if (route.request().method() !== "PATCH" || held) {
          await route.continue();
          return;
        }
        held = true;
        const response = await route.fetch();
        await canvasGone;
        await route.fulfill({ response });
      });

      const offCanvasSave = page.waitForResponse(isFlowWrite, {
        timeout: SAVE_WINDOW_MS,
      });
      await dragFirstNode(page);
      await page.getByTestId(`sidebar-nav-${section}`).click();
      await expect(page.locator(".react-flow__node")).toHaveCount(0);
      await expect.poll(() => held, { timeout: SAVE_WINDOW_MS }).toBe(true);
      releaseResponse();
      expect((await offCanvasSave).status()).toBe(200);

      await page.getByTestId("sidebar-nav-components").click();
      const nextSave = page.waitForResponse(isFlowWrite, {
        timeout: SAVE_WINDOW_MS,
      });
      await dragFirstNode(page);
      expect((await nextSave).status()).toBe(200);

      expect(statuses).not.toContain(409);
      await expect(page.getByTestId("flow-conflict-banner")).toBeHidden();
    },
  );
}
