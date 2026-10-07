import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";
import { lockFlow, unlockFlow } from "../../utils/lock-flow";
import { unselectNodes } from "../../utils/unselect-nodes";

test(
  "user must be able to lock a flow and it must be saved",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    // Four lock/unlock round trips, each a settings save plus a full editor
    // reload, then twenty click-and-assert iterations. That is ~1 minute on
    // Linux/macOS and lands right on the 5-minute wall on Windows CI, where
    // every step costs 3-5x as much — the test times out mid-loop rather than
    // finding anything. Nothing here is Windows-specific except the pace.
    test.slow(
      process.platform === "win32",
      "Windows CI runners are 3-5x slower",
    );

    await openStarterProject(page, TEXTS.templateBasicPrompting);
    const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
    if (!flowId) {
      throw new Error(
        `Expected a flow URL after opening the starter project; got ${page.url()}`,
      );
    }

    await lockFlow(page);

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.goto(`/flow/${flowId}`);
    await waitForFlowEditorReady(page);

    //ensure the UI is updated

    await unlockFlow(page);

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.goto(`/flow/${flowId}`);
    await waitForFlowEditorReady(page);

    await tryDeleteEdge(page);

    // Delete edges one by one (when unlocked, should work)
    await deleteFirstEdge(page, 2);
    await deleteFirstEdge(page, 1);
    await deleteFirstEdge(page, 0);

    await tryConnectNodes(page);

    await unselectNodes(page);

    await page.getByText(TEXTS.componentChatInput, { exact: true }).click();

    await adjustScreenView(page);

    await page.getByTestId("handle-prompt-shownode-prompt-right").click();
    await page
      .getByTestId("handle-languagemodelcomponent-shownode-system message-left")
      .click();

    await page
      .getByTestId("handle-chatinput-shownode-chat message-right")
      .click();
    await page
      .getByTestId("handle-languagemodelcomponent-shownode-input-left")
      .click();

    await page
      .getByTestId(
        "handle-languagemodelcomponent-shownode-model response-right",
      )
      .click();
    await page.getByTestId("handle-chatoutput-shownode-inputs-left").click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  },
);

async function tryConnectNodes(page: Page) {
  await lockFlow(page);

  const numberOfTries = 5;
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);

  for (let i = 0; i < numberOfTries; i++) {
    try {
      await page.getByTestId("handle-prompt-shownode-prompt-right").click({
        timeout: 500,
      });
    } catch (_e) {
      await expect(page.locator(".react-flow__edge")).toHaveCount(0);
    }

    try {
      await page
        .getByTestId(
          "handle-languagemodelcomponent-shownode-system message-left",
        )
        .click({
          timeout: 500,
        });
    } catch (_e) {
      await expect(page.locator(".react-flow__edge")).toHaveCount(0);
    }
    await expect(page.locator(".react-flow__edge")).toHaveCount(0);
  }
  await unlockFlow(page);
}

async function deleteFirstEdge(page: Page, expectedRemaining: number) {
  const edges = page.locator(".react-flow__edge");
  const selectedEdges = page.locator(".react-flow__edge.selected");
  // A bezier edge's bounding-box center is not always on its stroke, so a
  // single click can miss the edge and select nothing — Backspace then
  // silently deletes nothing. Re-click until an edge is actually selected.
  await expect(async () => {
    await edges.nth(0).click();
    await expect(selectedEdges).not.toHaveCount(0, { timeout: 1000 });
  }).toPass({ timeout: TIMEOUTS.standard });
  await page.keyboard.press("Backspace");
  await expect(edges).toHaveCount(expectedRemaining);
}

async function tryDeleteEdge(page: Page) {
  await lockFlow(page);

  await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  const numberOfTries = 5;

  // When locked, clicking edges and pressing delete should not remove them
  for (let i = 0; i < numberOfTries; i++) {
    await page.locator(".react-flow__edge").nth(0).click();
    await page.keyboard.press("Backspace");
    await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  }
  await unlockFlow(page);
}
