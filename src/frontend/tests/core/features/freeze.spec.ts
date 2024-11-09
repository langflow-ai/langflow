import { expect, test } from "@playwright/test";

test("user must be able to freeze a component", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

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
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();

  //first component

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("text input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //second component

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("url");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("dataURL")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //third component

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("split text");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersSplit Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fourth component

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("parse data");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fifth component

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  let filledApiKey = await page.getByTestId("remove-icon-badge").count();
  while (filledApiKey > 0) {
    await page.getByTestId("remove-icon-badge").first().click();
    await page.waitForTimeout(1000);
    filledApiKey = await page.getByTestId("remove-icon-badge").count();
  }

  await page.getByTestId("fit_view").click();

  //connection 1
  const urlOutput = await page
    .getByTestId("handle-url-shownode-data-right")
    .nth(0);
  await urlOutput.hover();
  await page.mouse.down();
  const splitTextInputData = await page.getByTestId(
    "handle-splittext-shownode-data inputs-left",
  );
  await splitTextInputData.hover();
  await page.mouse.up();

  //connection 2
  const textOutput = await page
    .getByTestId("handle-textinput-shownode-text-right")
    .nth(0);
  await textOutput.hover();
  await page.mouse.down();
  const splitTextInput = await page.getByTestId(
    "handle-splittext-shownode-separator-left",
  );
  await splitTextInput.hover();
  await page.mouse.up();

  await page.getByTestId("fit_view").click();

  //connection 3
  const splitTextOutput = await page
    .getByTestId("handle-splittext-shownode-chunks-right")
    .nth(0);
  await splitTextOutput.hover();
  await page.mouse.down();
  const parseDataInput = await page.getByTestId(
    "handle-parsedata-shownode-data-left",
  );
  await parseDataInput.hover();
  await page.mouse.up();

  //connection 4
  const parseDataOutput = await page
    .getByTestId("handle-parsedata-shownode-text-right")
    .nth(0);
  await parseDataOutput.hover();
  await page.mouse.down();
  const chatOutputInput = await page.getByTestId(
    "handle-chatoutput-shownode-text-left",
  );
  await chatOutputInput.hover();
  await page.mouse.up();

  await page.getByTestId("fit_view").click();

  await page
    .getByTestId("textarea_str_input_value")
    .first()
    .fill("lorem ipsum");

  await page
    .getByTestId("inputlist_str_urls_0")
    .fill("https://www.lipsum.com/");

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("output-inspection-message").first().click();

  await page.getByRole("gridcell").nth(4).click();

  const firstRunWithoutFreezing = await page
    .getByPlaceholder("Empty")
    .textContent();

  await page.getByText("Close").last().click();
  await page.getByText("Close").last().click();

  await page.getByTestId("textarea_str_input_value").first().fill(",");

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("output-inspection-message").first().click();

  await page.getByRole("gridcell").nth(4).click();

  const secondRunWithoutFreezing = await page
    .getByPlaceholder("Empty")
    .textContent();

  await page.getByText("Close").last().click();
  await page.getByText("Close").last().click();

  await page.getByText("Split Text", { exact: true }).click();

  await page.waitForTimeout(1000);

  await page.getByTestId("more-options-modal").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-Snowflake").click();

  await page.waitForTimeout(1000);

  await page.keyboard.press("Escape");

  await page.locator('//*[@id="react-flow-id"]').click();

  await page
    .getByTestId("textarea_str_input_value")
    .first()
    .fill("lorem ipsum");

  await page.waitForTimeout(1000);

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("output-inspection-message").first().click();

  await page.getByRole("gridcell").nth(4).click();

  const firstTextFreezed = await page.getByPlaceholder("Empty").textContent();

  await page.getByText("Close").last().click();
  await page.getByText("Close").last().click();

  await page.getByText("Split Text", { exact: true }).click();

  await page.waitForTimeout(1000);

  await page.getByTestId("more-options-modal").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-Snowflake").last().click();

  await page.waitForTimeout(1000);

  await page.keyboard.press("Escape");

  await page.locator('//*[@id="react-flow-id"]').click();

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("output-inspection-message").first().click();

  await page.getByRole("gridcell").nth(4).click();

  const thirdTextWithoutFreezing = await page
    .getByPlaceholder("Empty")
    .textContent();

  expect(secondRunWithoutFreezing).toBe(firstTextFreezed);

  expect(firstRunWithoutFreezing).not.toBe(firstTextFreezed);
  expect(firstRunWithoutFreezing).not.toBe(secondRunWithoutFreezing);
  expect(firstRunWithoutFreezing).not.toBe(firstTextFreezed);
  expect(thirdTextWithoutFreezing).not.toBe(firstTextFreezed);
});
