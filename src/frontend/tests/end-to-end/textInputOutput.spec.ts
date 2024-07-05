import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("TextInputOutputComponent", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.waitForTimeout(2000);

  let modalCount = 0;
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

  const focusElementsOnBoard = async ({ page }) => {
    const focusElements = await page.getByTestId("extended-disclosure");
    focusElements.click();
  };

  await focusElementsOnBoard({ page });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("openai");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  let visibleElementHandle;

  const elementsTextInputOutput = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .all();

  for (const element of elementsTextInputOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.waitFor({
    state: "visible",
    timeout: 30000,
  });

  await visibleElementHandle.hover();
  await page.mouse.down();

  for (const element of elementsTextInputOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.waitFor({
    state: "visible",
    timeout: 30000,
  });

  // Move to the second element
  await visibleElementHandle.hover();

  // Release the mouse
  await page.mouse.up();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text output");

  await page
    .getByTestId("outputsText Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const elementsOpenAiOutput = await page
    .getByTestId("handle-openaimodel-shownode-text-right")
    .all();

  for (const element of elementsOpenAiOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.waitFor({
    state: "visible",
    timeout: 30000,
  });

  // Click and hold on the first element
  await visibleElementHandle.hover();
  await page.mouse.down();

  const elementTextOutputInput = await page
    .getByTestId("handle-textoutput-shownode-text-left")
    .all();

  for (const element of elementTextOutputInput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.waitFor({
    state: "visible",
    timeout: 30000,
  });

  // Move to the second element
  await visibleElementHandle.hover();

  // Release the mouse
  await page.mouse.up();

  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(0)
    .fill("This is a test!");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown-model_name").click();
  await page.getByTestId("gpt-4o-0-option").click();

  await page.waitForTimeout(2000);
  await page.getByText("Playground", { exact: true }).click();
  await page.getByText("Run Flow", { exact: true }).click();

  await page.waitForTimeout(5000);

  let textInputContent = await page
    .getByPlaceholder("Enter text...")
    .textContent();
  expect(textInputContent).toBe("This is a test!");

  await page.getByText("Outputs", { exact: true }).nth(1).click();
  await page.getByText("Text Output", { exact: true }).nth(2).click();
  let contentOutput = await page.getByPlaceholder("Enter text...").inputValue();
  expect(contentOutput).not.toBe(null);

  await page.keyboard.press("Escape");

  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(0)
    .fill("This is a test, again just to be sure!");
  await page.getByText("Playground", { exact: true }).click();
  await page.getByText("Run Flow", { exact: true }).click();

  await page.waitForTimeout(5000);

  textInputContent = await page.getByPlaceholder("Enter text...").textContent();
  expect(textInputContent).toBe("This is a test, again just to be sure!");

  await page.getByText("Outputs", { exact: true }).nth(1).click();
  await page.getByText("Text Output", { exact: true }).nth(2).click();
  contentOutput = await page.getByPlaceholder("Enter text...").inputValue();
  expect(contentOutput).not.toBe(null);
});
