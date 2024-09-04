import { expect, test } from "@playwright/test";

test("user must be able to stop a building", async ({ page }) => {
  await page.goto("/");
  // await page.waitForTimeout(2000);

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
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Blank Flow" }).click();

  //first component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text input");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //second component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("url");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("dataURL")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //third component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("split text");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersSplit Text")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fourth component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("parse data");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fifth component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat output");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
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
    // await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page.getByTitle("fit view").click();

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

  await page.getByTitle("fit view").click();

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

  await page.getByTitle("fit view").click();

  await page.getByTestId("textarea_str_input_value").first().fill(",");

  await page
    .getByTestId("inputlist_str_urls_0")
    .fill("https://www.nature.com/articles/d41586-023-02870-5");

  await page.getByTestId("int_int_chunk_size").fill("2");
  await page.getByTestId("int_int_chunk_overlap").fill("1");

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=Building", {
    timeout: 100000,
  });

  await page.waitForSelector('[data-testid="loading_icon"]', {
    timeout: 100000,
  });

  expect(
    await page.getByTestId("loading_icon").last().isVisible(),
  ).toBeTruthy();
  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeTruthy();

  await page.getByTestId("stop_building_button").click();

  await page.waitForTimeout(1000);

  expect(await page.getByTestId("loading_icon").isHidden()).toBeTruthy();
  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeFalsy();

  await page.waitForSelector("text=Saved", {
    timeout: 100000,
  });

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=Building", {
    timeout: 100000,
  });

  await page.waitForSelector('[data-testid="loading_icon"]', {
    timeout: 100000,
  });

  await page.waitForSelector("text=Building", {
    timeout: 100000,
  });

  expect(await page.getByText("Building").isVisible()).toBeTruthy();

  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeTruthy();

  await page.waitForSelector("text=Building", {
    timeout: 100000,
  });

  expect(await page.getByText("Building").isVisible()).toBeTruthy();

  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeTruthy();

  await page.getByTestId("stop_building_button").click();

  await page.waitForSelector("text=Saved", {
    timeout: 100000,
  });

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector('[data-testid="loading_icon"]', {
    timeout: 100000,
  });

  await page.waitForSelector("text=Building", {
    timeout: 100000,
  });

  expect(await page.getByText("Building").isVisible()).toBeTruthy();

  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeTruthy();

  await page.getByTestId("stop_building_button").click();

  await page.waitForSelector("text=Saved", {
    timeout: 100000,
  });

  expect(
    await page.getByTestId("stop_building_button").isEnabled(),
  ).toBeFalsy();
});
