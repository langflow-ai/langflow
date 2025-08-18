import { test } from "@playwright/test";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";
import { updateOldComponents } from "../../utils/update-old-components";
import { zoomOut } from "../../utils/zoom-out";

// TODO: fix this test
test(
  "user must be able to stop a building",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //first component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 0, y: 0 },
      });

    await zoomOut(page, 3);

    //second component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 200 },
      });

    //third component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("split text");

    await page
      .getByTestId("processingSplit Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    //fourth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("data to message");

    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 500 },
      });

    //fifth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 600, y: 300 },
      });

    await updateOldComponents(page);
    await removeOldApiKeys(page);

    await page.getByTestId("fit_view").click();

    await zoomOut(page, 2);

    //connection 1
    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .click();
    await page.getByTestId("handle-splittext-shownode-input-left").click();

    //connection 2
    await page
      .getByTestId("handle-textinput-shownode-output text-right")
      .click();
    await page.getByTestId("handle-splittext-shownode-separator-left").click();

    //connection 3
    await page.getByTestId("handle-splittext-shownode-chunks-right").click();
    await page.getByTestId("handle-parsedata-shownode-data-left").click();

    //connection 4
    await page.getByTestId("handle-parsedata-shownode-message-right").click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .click();

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
    documentation: str = "https://docs.langflow.org/components-custom-components"
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
