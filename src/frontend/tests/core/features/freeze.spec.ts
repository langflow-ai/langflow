import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to freeze a component",
  { tag: ["@release", "@workspace", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    //first component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="inputsText Input"]', {
      timeout: 1000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("inputsText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    //third component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("split text");
    await page.waitForSelector('[data-testid="processingSplit Text"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingSplit Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 100 },
      });

    //fourth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("parse data");
    await page.waitForSelector('[data-testid="processingParse Data"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingParse Data")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 300 },
      });

    await page.getByTestId("zoom_out").click();

    //fifth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 600, y: 200 },
      });

    await page.getByTestId("div-generic-node").nth(4).click();

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    await page.getByTestId("fit_view").click();

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      await page.waitForSelector('[data-testid="icon-AlertTriangle"]', {
        timeout: 1000,
      });
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page.getByTestId("fit_view").click();
    await zoomOut(page, 2);

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

    await page.waitForSelector('[data-testid="output-inspection-message"]', {
      timeout: 1000,
    });

    await page.getByTestId("output-inspection-message").first().click();

    await page.getByRole("gridcell").nth(4).click();

    const firstRunWithoutFreezing = await page
      .getByPlaceholder("Empty")
      .textContent();

    await page.getByText("Close").last().click();

    await page.getByTestId("btn-close-modal").click();

    await page.getByTestId("textarea_str_input_value").first().fill(",");

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.waitForSelector('[data-testid="output-inspection-message"]', {
      timeout: 1000,
    });

    await page.getByTestId("output-inspection-message").first().click();

    await page.getByRole("gridcell").nth(4).click();

    const secondRunWithoutFreezing = await page
      .getByPlaceholder("Empty")
      .textContent();

    await page.getByText("Close").last().click();
    await page.getByText("Close").last().click();

    await page.getByText("Split Text", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="icon-Snowflake"]', {
      timeout: 1000,
    });

    await page.getByTestId("icon-Snowflake").click();

    await page.keyboard.press("Escape");

    await page.locator('//*[@id="react-flow-id"]').click();

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill("lorem ipsum");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.waitForSelector('[data-testid="output-inspection-message"]', {
      timeout: 1000,
    });

    await page.getByTestId("output-inspection-message").first().click();

    await page.getByRole("gridcell").nth(4).click();

    const firstTextFreezed = await page.getByPlaceholder("Empty").textContent();

    await page.getByText("Close").last().click();
    await page.getByText("Close").last().click();

    await page.getByText("Split Text", { exact: true }).click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="icon-Snowflake"]', {
      timeout: 1000,
    });

    await page.getByText("Freeze", { exact: true }).click();

    await page.keyboard.press("Escape");

    await page.locator('//*[@id="react-flow-id"]').click();

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.waitForSelector('[data-testid="output-inspection-message"]', {
      timeout: 1000,
    });

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
  },
);
