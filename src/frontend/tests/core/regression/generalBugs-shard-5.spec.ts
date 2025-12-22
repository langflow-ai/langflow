import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "should be able to see output preview from grouped components and connect components with a single click",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const secondRandomName = Math.random().toString(36).substring(2);
    const thirdRandomName = Math.random().toString(36).substring(2);

    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {});

    await zoomOut(page, 4);

    await page.waitForTimeout(500);

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 150 },
      });

    await page.waitForTimeout(500);

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 670, y: 200 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("combine text");

    await page.waitForSelector('[data-testid="processingCombine Text"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("processingCombine Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 10, y: 10 },
      });

    await page.waitForTimeout(500);

    await page.getByTestId("popover-anchor-input-delimiter").fill("-");

    await page
      .getByTestId("processingCombine Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 10 },
      });

    await page.waitForTimeout(500);

    await page.getByTestId("popover-anchor-input-delimiter").last().fill("-");

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text");

    await page.waitForSelector('[data-testid="input_outputText Output"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 10, y: 400 },
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

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    expect(
      await page
        .getByTestId("output-inspection-combined text-groupnode")
        .first(),
    ).not.toBeDisabled();
    await page
      .getByTestId("output-inspection-combined text-groupnode")
      .first()
      .click();

    await page.getByText("Component Output").isVisible();

    const text = await page.getByPlaceholder("Empty").textContent();

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
