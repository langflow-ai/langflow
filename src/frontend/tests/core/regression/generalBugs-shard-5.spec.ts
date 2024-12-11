import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should be able to see output preview from grouped components and connect components with a single click",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const secondRandomName = Math.random().toString(36).substring(2);
    const thirdRandomName = Math.random().toString(36).substring(2);

    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="inputsText Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("inputsText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {});

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page
      .getByTestId("inputsText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 150 },
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

    await page
      .getByTestId("processingCombine Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 10 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text");

    await page.waitForSelector('[data-testid="outputsText Output"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("outputsText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 10, y: 400 },
      });
    //connection 1
    const elementCombineTextOutput0 = page
      .getByTestId("div-handle-combinetext-shownode-combined text-right")
      .nth(0);
    await elementCombineTextOutput0.click();

    const blockedHandle = page
      .getByTestId("div-handle-textinput-shownode-text-right")
      .first();
    const secondBlockedHandle = page
      .getByTestId("div-handle-combinetext-shownode-combined text-right")
      .nth(3);
    const thirdBlockedHandle = page
      .getByTestId("div-handle-textoutput-shownode-text-right")
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

    expect(hasGradient).toBe(true);
    expect(secondHasGradient).toBe(true);
    expect(thirdHasGradient).toBe(true);

    const unlockedHandle = page
      .getByTestId("div-handle-textinput-shownode-text-left")
      .last();
    const secondUnlockedHandle = page
      .getByTestId("div-handle-combinetext-shownode-second text-left")
      .last();
    const thirdUnlockedHandle = page
      .getByTestId("div-handle-combinetext-shownode-second text-left")
      .first();
    const fourthUnlockedHandle = page
      .getByTestId("div-handle-textoutput-shownode-text-left")
      .first();

    const hasGradientUnlocked = await unlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundImage.includes("conic-gradient") &&
        style.backgroundImage.includes("rgb(79, 70, 229)")
      );
    });

    const secondHasGradientUnlocked = await secondUnlockedHandle?.evaluate(
      (el) => {
        const style = window.getComputedStyle(el);
        return (
          style.backgroundImage.includes("conic-gradient") &&
          style.backgroundImage.includes("rgb(79, 70, 229)")
        );
      },
    );

    const thirdHasGradientLocked = await thirdUnlockedHandle?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(228, 228, 231)";
    });

    const fourthHasGradientUnlocked = await fourthUnlockedHandle?.evaluate(
      (el) => {
        const style = window.getComputedStyle(el);
        return (
          style.backgroundImage.includes("conic-gradient") &&
          style.backgroundImage.includes("rgb(79, 70, 229)")
        );
      },
    );

    expect(hasGradientUnlocked).toBe(true);
    expect(secondHasGradientUnlocked).toBe(true);
    expect(thirdHasGradientLocked).toBe(true);
    expect(fourthHasGradientUnlocked).toBe(true);

    const elementCombineTextInput1 = await page
      .getByTestId("handle-combinetext-shownode-first text-left")
      .nth(1);
    await elementCombineTextInput1.click();

    await page
      .getByTestId("title-Combine Text")
      .first()
      .click({ modifiers: ["Control"] });
    await page
      .getByTestId("title-delimiter")
      .last()
      .click({ modifiers: ["Control"] });

    await page.getByRole("button", { name: "Group" }).click();

    await page.getByTitle("fit view").click();

    //connection 2
    const elementTextOutput0 = page
      .getByTestId("handle-textinput-shownode-text-right")
      .nth(0);
    await elementTextOutput0.click();
    const elementGroupInput0 = page.getByTestId(
      "handle-groupnode-shownode-first text-left",
    );
    await elementGroupInput0.click();

    //connection 3
    const elementTextOutput1 = page
      .getByTestId("handle-textinput-shownode-text-right")
      .nth(2);
    await elementTextOutput1.click();

    const elementGroupInput1 = page
      .getByTestId("handle-groupnode-shownode-second text-left")
      .nth(1);
    await elementGroupInput1.click();

    //connection 4
    const elementGroupOutput = page
      .getByTestId("handle-groupnode-shownode-combined text-right")
      .nth(0);
    await elementGroupOutput.click();
    const elementTextOutputInput = page
      .getByTestId("handle-textoutput-shownode-text-left")
      .nth(0);

    await elementTextOutputInput.click();

    await page.getByTestId("textarea_str_input_value").nth(0).fill(randomName);

    await page
      .getByTestId("textarea_str_input_value")
      .nth(1)
      .fill(secondRandomName);

    await page
      .getByPlaceholder("Type something...", { exact: true })
      .nth(4)
      .fill(thirdRandomName);

    await page
      .getByPlaceholder("Type something...", { exact: true })
      .nth(3)
      .fill("-");

    await page
      .getByPlaceholder("Type something...", { exact: true })
      .nth(2)
      .fill("-");

    await page.getByTestId("button_run_text output").last().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    expect(
      await page.getByTestId("output-inspection-combined text").first(),
    ).not.toBeDisabled();
    await page.getByTestId("output-inspection-combined text").first().click();

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
