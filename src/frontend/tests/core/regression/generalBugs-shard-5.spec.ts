import { expect, test } from "@playwright/test";

test("should be able to see output preview from grouped components and connect components with a single click", async ({
  page,
}) => {
  await page.goto("/");

  let modalCount = 0;
  const randomName = Math.random().toString(36).substring(2);
  const secondRandomName = Math.random().toString(36).substring(2);
  const thirdRandomName = Math.random().toString(36).substring(2);

  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("text input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 100);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("combine text");
  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 100);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("processingCombine Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 100);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("processingCombine Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 100);
      await page.waitForTimeout(200);
    });

  await page.mouse.up();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("text output");
  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 100);
    });

  await page.mouse.up();

  await page
    .getByTestId("outputsText Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("fit_view").click({
    force: true,
  });
  await page.waitForTimeout(500);

  //connection 1
  const elementCombineTextOutput0 = await page
    .getByTestId("div-handle-combinetext-shownode-combined text-right")
    .nth(0);
  await elementCombineTextOutput0.click();

  const blockedHandle = await page
    .getByTestId("div-handle-textinput-shownode-text-right")
    .nth(2);
  const secondBlockedHandle = await page
    .getByTestId("div-handle-combinetext-shownode-combined text-right")
    .nth(2);
  const thirdBlockedHandle = await page
    .getByTestId("div-handle-textoutput-shownode-text-right")
    .nth(0);

  const hasGradient = await blockedHandle?.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return style.backgroundColor === "rgb(228, 228, 231)";
  });

  await page.waitForTimeout(500);

  const secondHasGradient = await secondBlockedHandle?.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return style.backgroundColor === "rgb(228, 228, 231)";
  });

  await page.waitForTimeout(500);

  const thirdHasGradient = await thirdBlockedHandle?.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return style.backgroundColor === "rgb(228, 228, 231)";
  });

  await page.waitForTimeout(500);

  expect(hasGradient).toBe(true);
  expect(secondHasGradient).toBe(true);
  expect(thirdHasGradient).toBe(true);

  const unlockedHandle = await page
    .getByTestId("div-handle-textinput-shownode-text-left")
    .last();
  const secondUnlockedHandle = await page
    .getByTestId("div-handle-combinetext-shownode-second text-left")
    .last();
  const thirdUnlockedHandle = await page
    .getByTestId("div-handle-combinetext-shownode-second text-left")
    .first();
  const fourthUnlockedHandle = await page
    .getByTestId("div-handle-textoutput-shownode-text-left")
    .first();

  const hasGradientUnlocked = await unlockedHandle?.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return (
      style.backgroundImage.includes("conic-gradient") &&
      style.backgroundImage.includes("rgb(79, 70, 229)")
    );
  });

  await page.waitForTimeout(500);

  const secondHasGradientUnlocked = await secondUnlockedHandle?.evaluate(
    (el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundImage.includes("conic-gradient") &&
        style.backgroundImage.includes("rgb(79, 70, 229)")
      );
    },
  );

  await page.waitForTimeout(500);

  const thirdHasGradientLocked = await thirdUnlockedHandle?.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return style.backgroundColor === "rgb(228, 228, 231)";
  });

  await page.waitForTimeout(500);

  const fourthHasGradientUnlocked = await fourthUnlockedHandle?.evaluate(
    (el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundImage.includes("conic-gradient") &&
        style.backgroundImage.includes("rgb(79, 70, 229)")
      );
    },
  );

  await page.waitForTimeout(500);

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

  await page.waitForTimeout(500);

  await page.getByTitle("fit view").click();

  await page.waitForTimeout(500);

  //connection 2
  const elementTextOutput0 = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .nth(0);
  await elementTextOutput0.click();
  const elementGroupInput0 = await page.getByTestId(
    "handle-groupnode-shownode-first text-left",
  );
  await elementGroupInput0.click();

  //connection 3
  const elementTextOutput1 = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .nth(2);
  await elementTextOutput1.click();
  const elementGroupInput1 = await page
    .getByTestId("handle-groupnode-shownode-second text-left")
    .nth(1);
  await elementGroupInput1.click();

  //connection 4
  const elementGroupOutput = await page
    .getByTestId("handle-groupnode-shownode-combined text-right")
    .nth(0);
  await elementGroupOutput.click();
  const elementTextOutputInput = await page
    .getByTestId("handle-textoutput-shownode-text-left")
    .nth(0);

  await elementTextOutputInput.click();

  await page.getByTestId("textarea_str_input_value").nth(0).fill(randomName);

  await page.waitForTimeout(500);
  await page
    .getByTestId("textarea_str_input_value")
    .nth(1)
    .fill(secondRandomName);
  await page.waitForTimeout(500);

  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(4)
    .fill(thirdRandomName);
  await page.waitForTimeout(500);

  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(3)
    .fill("-");
  await page.waitForTimeout(500);

  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(2)
    .fill("-");

  await page.waitForTimeout(500);

  await page.getByTestId("button_run_text output").last().click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });
  await page.waitForTimeout(500);

  expect(
    await page.getByTestId("output-inspection-combined text").first(),
  ).not.toBeDisabled();
  await page.getByTestId("output-inspection-combined text").first().click();
  await page.waitForTimeout(500);

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
});
