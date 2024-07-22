import { expect, test } from "@playwright/test";

test("should be able to see output preview from grouped components", async ({
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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-1000, 500);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("combine text");
  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-1000, 800);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("helpersCombine Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 800);
      await page.waitForTimeout(400);
    });

  await page.mouse.up();

  await page
    .getByTestId("helpersCombine Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 800);
      await page.waitForTimeout(200);
    });

  await page.mouse.up();

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text output");
  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-200, 500);
    });

  await page.mouse.up();

  await page
    .getByTestId("outputsText Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("fit view").click({
    force: true,
  });

  //connection 1
  const elementCombineTextOutput0 = await page
    .getByTestId("handle-combinetext-shownode-combined text-right")
    .nth(0);
  await elementCombineTextOutput0.hover();
  await page.mouse.down();
  const elementCombineTextInput1 = await page
    .getByTestId("handle-combinetext-shownode-first text-left")
    .nth(1);
  await elementCombineTextInput1.hover();
  await page.mouse.up();

  await page
    .getByTestId("title-Combine Text")
    .first()
    .click({ modifiers: ["Control"] });
  await page
    .getByTestId("title-Combine Text")
    .last()
    .click({ modifiers: ["Control"] });

  await page.getByRole("button", { name: "Group" }).click();

  //connection 2
  const elementTextOutput0 = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .nth(0);
  await elementTextOutput0.hover();
  await page.mouse.down();
  const elementGroupInput0 = await page.getByTestId(
    "handle-groupnode-shownode-first text-left",
  );

  await elementGroupInput0.hover();
  await page.mouse.up();

  //connection 3
  const elementTextOutput1 = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .nth(2);
  await elementTextOutput1.hover();
  await page.mouse.down();
  const elementGroupInput1 = await page
    .getByTestId("handle-groupnode-shownode-second text-left")
    .nth(1);

  await elementGroupInput1.hover();
  await page.mouse.up();

  //connection 4
  const elementGroupOutput = await page
    .getByTestId("handle-groupnode-shownode-combined text-right")
    .nth(0);
  await elementGroupOutput.hover();
  await page.mouse.down();
  const elementTextOutputInput = await page
    .getByTestId("handle-textoutput-shownode-text-left")
    .nth(0);

  await elementTextOutputInput.hover();
  await page.mouse.up();

  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(0)
    .fill(randomName);
  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(1)
    .fill(secondRandomName);
  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(6)
    .fill(thirdRandomName);

  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(3)
    .fill("-");
  await page
    .getByPlaceholder("Type something...", { exact: true })
    .nth(4)
    .fill("-");

  await page.waitForTimeout(3000);

  await page.getByTestId("button_run_text output").last().click();

  await page.waitForSelector("text=Text Output built successfully", {
    timeout: 30000,
  });

  await page.waitForTimeout(3000);

  expect(
    await page.getByTestId("output-inspection-combined text").first(),
  ).not.toBeDisabled();
  await page.getByTestId("output-inspection-combined text").first().click();

  await page.getByText("Component Output").isVisible();

  const text = await page.getByPlaceholder("Empty").textContent();
  expect(text).toBe(`${randomName}-${secondRandomName}-${thirdRandomName}`);
});
