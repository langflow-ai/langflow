import { test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// TODO: fix this test
test(
  "user must be able to stop a building",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    //first component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");

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

    await page
      .getByTestId("processingSplit Text")
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

    await page
      .getByTestId("processingParse Data")
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

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
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

    await page.getByTestId("textarea_str_input_value").first().fill(",");

    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://www.nature.com/articles/d41586-023-02870-5");

    await page.getByTestId("int_int_chunk_size").fill("2");
    await page.getByTestId("int_int_chunk_overlap").fill("1");

    const timerCode = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import time

class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "custom_components"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        time.sleep(10000)
        data = Data(value=self.input_value)
        self.status = data
        return data
  `;

    await page.getByTestId("sidebar-custom-component-button").click();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("title-Custom Component").first().click();

    await page.waitForSelector('[data-testid="code-button-modal"]', {
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").click();

    await page.waitForSelector('[id="checkAndSaveBtn"]', {
      timeout: 3000,
    });

    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(timerCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();
    await page.waitForTimeout(500);

    await page.getByTestId("button_run_custom component").click();

    await page.waitForSelector("text=running", {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="stop_building_button"]', {
      timeout: 100000,
    });

    await page.getByTestId("stop_building_button").last().click();

    await page.waitForSelector("text=build stopped", {
      timeout: 100000,
    });
  },
);
