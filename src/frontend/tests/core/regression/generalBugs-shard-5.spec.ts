import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { zoomOut } from "../../utils/zoom-out";

async function addComponentAtPosition(
  page: Page,
  options: {
    search: string;
    testId: string;
    position: { x: number; y: number };
  },
): Promise<void> {
  const nodes = page.locator(".react-flow__node");
  const previousNodeCount = await nodes.count();
  await addComponentFromSidebar(page, {
    search: options.search,
    testId: options.testId,
    hoverAdd: true,
  });

  const node = nodes.nth(previousNodeCount);
  const dragHandle = node.getByTestId("generic-node-title-arrangement");
  const before = await node.boundingBox();
  const handleBox = await dragHandle.boundingBox();
  const canvasBox = await page.locator("#react-flow-id").boundingBox();
  if (!before || !handleBox || !canvasBox) {
    throw new Error("Expected an attached graph node with a draggable title");
  }

  const startX = handleBox.x + handleBox.width / 2;
  const startY = handleBox.y + handleBox.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(
    canvasBox.x + options.position.x,
    canvasBox.y + options.position.y,
    { steps: 12 },
  );
  await page.mouse.up();

  await expect
    .poll(async () => {
      const after = await node.boundingBox();
      return after ? Math.hypot(after.x - before.x, after.y - before.y) : 0;
    })
    .toBeGreaterThan(20);
}

test(
  "should be able to see output preview from grouped components and connect components with a single click",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const secondRandomName = Math.random().toString(36).substring(2);
    const thirdRandomName = Math.random().toString(36).substring(2);

    await openBlankFlow(page);
    await addLegacyComponents(page);

    await addComponentAtPosition(page, {
      search: TEXTS.searchTextInput,
      testId: "input_outputText Input",
      position: { x: 200, y: 200 },
    });

    await zoomOut(page, 4);

    await addComponentAtPosition(page, {
      search: TEXTS.searchTextInput,
      testId: "input_outputText Input",
      position: { x: 500, y: 150 },
    });

    await addComponentAtPosition(page, {
      search: TEXTS.searchTextInput,
      testId: "input_outputText Input",
      position: { x: 670, y: 200 },
    });

    await addComponentAtPosition(page, {
      search: "combine text",
      testId: "processingCombine Text",
      position: { x: 10, y: 10 },
    });

    await page.getByTestId("popover-anchor-input-delimiter").fill("-");

    await addComponentAtPosition(page, {
      search: "combine text",
      testId: "processingCombine Text",
      position: { x: 200, y: 10 },
    });

    await page.getByTestId("popover-anchor-input-delimiter").last().fill("-");

    await addComponentAtPosition(page, {
      search: "text",
      testId: "input_outputText Output",
      position: { x: 10, y: 400 },
    });
    //connection 1
    const elementCombineTextOutput0 = page
      .getByTestId("handle-combinetext-shownode-combined text-right")
      .nth(0);
    await elementCombineTextOutput0.click();

    const blockedHandle = page
      .getByTestId("handle-textinput-shownode-output text-right")
      .first();
    const secondBlockedHandle = page
      .getByTestId("handle-combinetext-shownode-combined text-right")
      .nth(1);
    const thirdBlockedHandle = page
      .getByTestId("handle-textoutput-shownode-output text-right")
      .first();

    const hasGradient = await blockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(228, 228, 231)";
    });

    const secondHasGradient = await secondBlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(228, 228, 231)";
    });

    const thirdHasGradient = await thirdBlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(228, 228, 231)";
    });

    expect(hasGradient).toBe(false);
    expect(secondHasGradient).toBe(false);
    expect(thirdHasGradient).toBe(false);

    const unlockedHandle = page
      .getByTestId("handle-textinput-shownode-text-left")
      .last();
    const secondUnlockedHandle = page
      .getByTestId("handle-combinetext-shownode-second text-left")
      .last();
    const thirdUnlockedHandle = page
      .getByTestId("handle-combinetext-shownode-second text-left")
      .first();
    const fourthUnlockedHandle = page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .first();

    const hasGradientUnlocked = await unlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(79, 70, 229)";
    });

    const secondHasGradientUnlocked = await secondUnlockedHandle?.evaluate(
      (el) => {
        const style = window.getComputedStyle(el);
        return style.backgroundColor === "rgb(79, 70, 229)";
      },
    );

    const thirdHasGradientLocked = await thirdUnlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(228, 228, 231)";
    });

    const fourthHasGradientUnlocked = await fourthUnlockedHandle?.evaluate(
      (el) => {
        const style = window.getComputedStyle(el);
        return style.backgroundColor === "rgb(79, 70, 229)";
      },
    );

    expect(hasGradientUnlocked).toBe(false);
    expect(secondHasGradientUnlocked).toBe(false);
    expect(thirdHasGradientLocked).toBe(false);
    expect(fourthHasGradientUnlocked).toBe(false);

    const elementCombineTextInput1 = await page
      .getByTestId("handle-combinetext-shownode-first text-left")
      .nth(1);
    await elementCombineTextInput1.click();

    await adjustScreenView(page, { numberOfZoomOut: 2 });

    // Select both Combine Text nodes using box selection (Shift+drag)
    // Note: Ctrl/Meta+click doesn't work reliably in Playwright with ReactFlow
    const combineTextNodes = page.locator(".react-flow__node").filter({
      has: page.getByTestId("title-Combine Text"),
    });

    const firstBox = await combineTextNodes.first().boundingBox();
    const secondBox = await combineTextNodes.nth(1).boundingBox();

    if (firstBox && secondBox) {
      // Calculate area to drag-select both nodes
      const startX = Math.min(firstBox.x, secondBox.x) - 50;
      const startY = Math.min(firstBox.y, secondBox.y) - 50;
      const endX =
        Math.max(firstBox.x + firstBox.width, secondBox.x + secondBox.width) +
        50;
      const endY =
        Math.max(firstBox.y + firstBox.height, secondBox.y + secondBox.height) +
        50;

      // Use Shift+drag for box selection
      await page.keyboard.down("Shift");
      await page.mouse.move(startX, startY);
      await page.mouse.down();
      await page.mouse.move(endX, endY, { steps: 10 });
      await page.mouse.up();
      await page.keyboard.up("Shift");
    }

    await page.waitForSelector('[data-testid="group-node"]', {
      timeout: 5000,
      state: "visible",
    });

    await page.getByTestId("group-node").click();

    //connection 1
    const elementTextOutput0 = page
      .getByTestId("handle-textinput-shownode-output text-right")
      .nth(0);
    await elementTextOutput0.click();
    const elementGroupInput0 = page.getByTestId(
      "handle-groupnode-shownode-first text-left",
    );
    await elementGroupInput0.click();

    //connection 2
    const elementTextOutput1 = page
      .getByTestId("handle-textinput-shownode-output text-right")
      .nth(2);
    await elementTextOutput1.click();
    const elementGroupInput1 = page
      .getByTestId("handle-groupnode-shownode-second text-left")
      .first();
    await elementGroupInput1.click();

    //connection 3
    const elementTextOutput2 = page
      .getByTestId("handle-textinput-shownode-output text-right")
      .nth(1);
    await elementTextOutput2.click();

    const elementGroupInput2 = page
      .getByTestId("handle-groupnode-shownode-second text-left")
      .nth(1)
      .last();
    await elementGroupInput2.click();

    //connection 4
    const elementGroupOutput = page
      .getByTestId("handle-groupnode-shownode-combined text-right")
      .nth(0);
    await elementGroupOutput.click();
    const elementTextOutputInput = page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .nth(0);

    await elementTextOutputInput.click();

    await page.getByTestId("textarea_str_input_value").nth(0).fill(randomName);

    await page
      .getByTestId("textarea_str_input_value")
      .nth(1)
      .fill(secondRandomName);

    await page
      .getByPlaceholder("Type something...", { exact: true })
      .nth(2)
      .fill(thirdRandomName);

    await page.getByTestId("button_run_text output").last().click();

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

    expect(
      await page
        .getByTestId("output-inspection-combined text-groupnode")
        .first(),
    ).not.toBeDisabled();
    await page
      .getByTestId("output-inspection-combined text-groupnode")
      .first()
      .click();

    await expect(page.getByText(TEXTS.componentOutput)).toBeVisible();
    const text = await page
      .getByPlaceholder(TEXTS.placeholderEmpty)
      .textContent();

    const permutations = [
      `${randomName}-${secondRandomName}-${thirdRandomName}`,
      `${randomName}-${thirdRandomName}-${secondRandomName}`,
      `${thirdRandomName}-${randomName}-${secondRandomName}`,
      `${thirdRandomName}-${secondRandomName}-${randomName}`,
      `${secondRandomName}-${randomName}-${thirdRandomName}`,
      `${secondRandomName}-${thirdRandomName}-${randomName}`,
    ];

    const isPermutationIncluded = permutations.some((permutation) =>
      text!.includes(permutation),
    );

    expect(isPermutationIncluded).toBe(true);
  },
);
