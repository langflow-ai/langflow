import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

const flowIdFrom = (page: Page): string => {
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  if (!flowId) throw new Error(`Expected a flow URL; got ${page.url()}`);
  return flowId;
};

async function saveLockFromSettings(page: Page, locked: boolean) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
    "data-state",
    locked ? "checked" : "unchecked",
  );
  await page.getByTestId("save-flow-settings").click();
  await expect(page.getByTestId("save-flow-settings")).toBeHidden({
    timeout: 30000,
  });
}

test(
  "should make the canvas editable right after unlocking a reloaded locked flow",
  { tag: ["@release"] },
  async ({ page }) => {
    await openStarterProject(page, TEXTS.templateBasicPrompting);
    const flowId = flowIdFrom(page);

    await saveLockFromSettings(page, true);
    await page.reload();
    await waitForFlowEditorReady(page);

    await saveLockFromSettings(page, false);

    const nodeCount = await page.locator(".react-flow__node").count();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 200 },
      });

    await expect(page.locator(".react-flow__node")).toHaveCount(nodeCount + 1);
    const persisted = await page.request.get(`/api/v1/flows/${flowId}`);
    expect(((await persisted.json()) as { locked?: boolean }).locked).toBe(
      false,
    );
  },
);
