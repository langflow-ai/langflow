import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "should process loop with update data correctly",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 3000,
      },
    );

    // Add URL component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 1000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    // Add Loop component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("loop");
    await page.waitForSelector('[data-testid="logicLoop"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("logicLoop")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 100 },
      });

    // Add Update Data component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("update data");
    await page.waitForSelector('[data-testid="processingUpdate Data"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingUpdate Data")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 100 },
      });

    // Add Parse Data component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("data to message");
    await page.waitForSelector('[data-testid="processingData to Message"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 700, y: 100 },
      });

    //This one is for testing the wrong loop message
    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 700, y: 400 },
      });

    const secondParseDataOutput = await page
      .getByTestId("handle-parsedata-shownode-data list-right")
      .nth(2);

    const loopItemInput = await page
      .getByTestId("handle-loopcomponent-shownode-item-left")
      .first();

    // Connecting the second parse data to the loop item to test the wrong loop message

    await secondParseDataOutput.hover();
    await page.mouse.down();
    await loopItemInput.hover();
    await page.mouse.up();

    // Add Chat Output component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 900, y: 100 },
      });

    await page.getByTestId("fit_view").click();

    await zoomOut(page, 2);

    // Loop Item -> Update Data

    const loopItemHandle = await page
      .getByTestId("handle-loopcomponent-shownode-item-right")
      .first();
    const updateDataInput = await page
      .getByTestId("handle-updatedata-shownode-data-left")
      .first();

    await loopItemHandle.hover();
    await page.mouse.down();
    await updateDataInput.hover();
    await page.mouse.up();

    // URL -> Loop Data
    const urlOutput = await page
      .getByTestId("handle-url-shownode-data-right")
      .first();
    const loopInput = await page
      .getByTestId("handle-loopcomponent-shownode-data-left")
      .first();

    await urlOutput.hover();
    await page.mouse.down();
    await loopInput.hover();
    await page.mouse.up();

    // Loop Done -> Parse Data
    const loopDoneHandle = await page
      .getByTestId("handle-loopcomponent-shownode-done-right")
      .first();
    const parseDataInput = await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .first();

    await loopDoneHandle.hover();
    await page.mouse.down();
    await parseDataInput.hover();
    await page.mouse.up();

    await page.getByTestId("div-generic-node").nth(5).click();

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    // Parse Data -> Chat Output
    const parseDataOutput = await page
      .getByTestId("handle-parsedata-shownode-message-right")
      .first();

    const chatOutputInput = await page
      .getByTestId("handle-chatoutput-shownode-text-left")
      .first();

    await parseDataOutput.hover();
    await page.mouse.down();
    await chatOutputInput.hover();
    await page.mouse.up();

    await page.getByTestId("input-list-plus-btn_urls-0").click();

    // Configure components
    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://en.wikipedia.org/wiki/Artificial_intelligence");
    await page
      .getByTestId("inputlist_str_urls_1")
      .fill("https://en.wikipedia.org/wiki/Artificial_intelligence");

    await page.getByTestId("div-generic-node").nth(2).click();
    await page.getByTestId("int_int_number_of_fields").fill("1");
    await page.getByTestId("div-generic-node").nth(2).click();

    await page.getByTestId("keypair0").fill("text");
    await page.getByTestId("keypair100").fill("modified_value");

    // Build and run, expect the wrong loop message
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=The flow has an incomplete loop.", {
      timeout: 30000,
    });
    await page.getByText("The flow has an incomplete loop.").last().click({
      timeout: 15000,
    });

    // Delete the second parse data used to test

    await page.getByTestId("div-generic-node").nth(4).click();

    await page.getByTestId("more-options-modal").click();

    await page.getByText("Delete").first().click();

    // Update Data -> Loop Item (left side)
    const updateDataOutput = await page
      .getByTestId("handle-updatedata-shownode-data-right")
      .first();

    await updateDataOutput.hover();
    await page.mouse.down();
    await loopItemInput.hover();
    await page.mouse.up();

    // Build and run
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });
    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    // Verify output
    await page.waitForSelector(
      '[data-testid="output-inspection-message-chatoutput"]',
      {
        timeout: 1000,
      },
    );
    await page
      .getByTestId("output-inspection-message-chatoutput")
      .first()
      .click();

    const output = await page.getByPlaceholder("Empty").textContent();
    expect(output).toContain("modified_value");

    // Count occurrences of modified_value in output
    const matches = output?.match(/modified_value/g) || [];
    expect(matches).toHaveLength(2);
  },
);
