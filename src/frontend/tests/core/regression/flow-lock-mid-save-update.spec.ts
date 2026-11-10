import type { Page, Request } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";

type FlowPatch = { locked?: boolean };

const flowIdFrom = (page: Page): string => {
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  if (!flowId) throw new Error(`Expected a flow URL; got ${page.url()}`);
  return flowId;
};

const isFlowPatch = (request: Request, flowId: string): boolean =>
  request.method() === "PATCH" &&
  new URL(request.url()).pathname === `/api/v1/flows/${flowId}`;

const patchBody = (request: Request): FlowPatch | null => {
  try {
    return request.postDataJSON() as FlowPatch | null;
  } catch {
    return null;
  }
};

/**
 * Holds every node update the flow fires on open until `release()`, so the
 * test controls exactly when the canvas graph changes.
 */
async function holdNodeUpdates(page: Page) {
  let releaseUpdates: () => void = () => {};
  const updatesReleased = new Promise<void>((resolve) => {
    releaseUpdates = resolve;
  });
  let held = 0;
  let landed = 0;
  await page.route("**/api/v1/custom_component/update**", async (route) => {
    held += 1;
    const response = await route.fetch();
    await updatesReleased;
    await route.fulfill({ response });
    landed += 1;
  });
  return {
    held: () => held,
    landed: () => landed,
    release: () => releaseUpdates(),
  };
}

test(
  "should keep a lock saved while a node update lands mid-save",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    const updates = await holdNodeUpdates(page);

    await openStarterProject(page, TEXTS.templateBasicPrompting);
    await expect.poll(updates.held, { timeout: 30000 }).toBeGreaterThan(0);
    const flowId = flowIdFrom(page);

    // The lock PATCH is held until the node updates have been applied, so the
    // canvas graph changes while the settings save is in flight.
    await page.route(`**/api/v1/flows/${flowId}`, async (route) => {
      const request = route.request();
      if (
        !isFlowPatch(request, flowId) ||
        patchBody(request)?.locked !== true
      ) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      const heldCount = updates.held();
      updates.release();
      await expect.poll(updates.landed).toBe(heldCount);
      // The app applies the update response after the network event.
      await page.waitForTimeout(1000);
      await route.fulfill({ response });
    });

    const unlockRequests: FlowPatch[] = [];
    page.on("request", (request) => {
      if (
        isFlowPatch(request, flowId) &&
        patchBody(request)?.locked === false
      ) {
        unlockRequests.push(patchBody(request)!);
      }
    });

    await page.getByTestId("flow_name").click();
    const lockSwitch = page.getByTestId("lock-flow-switch");
    await lockSwitch.click();
    await expect(lockSwitch).toHaveAttribute("data-state", "checked");
    await page.getByTestId("save-flow-settings").click();
    await expect(page.getByTestId("save-flow-settings")).toBeHidden({
      timeout: 30000,
    });

    await page.getByTestId("flow_name").click();
    await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
      "data-state",
      "checked",
    );
    await page.getByTestId("cancel-flow-settings").click();
    await expect(page.getByTestId("save-flow-settings")).toBeHidden();

    const node = page.locator(".react-flow__node").first();
    const box = await node.boundingBox();
    if (!box) throw new Error("Expected a node on the canvas");
    await page.mouse.move(box.x + box.width / 2, box.y + 20);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 120, box.y + 80, {
      steps: 10,
    });
    await page.mouse.up();
    // Longer than the autosave debounce, so a stale save would have fired.
    await page.waitForTimeout(2000);

    expect(unlockRequests).toEqual([]);
    await expect(page.getByText("Failed to save flow")).toHaveCount(0);
    const persisted = await page.request.get(`/api/v1/flows/${flowId}`);
    expect(persisted.ok()).toBe(true);
    expect(((await persisted.json()) as FlowPatch).locked).toBe(true);
  },
);
