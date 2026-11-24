import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { replaceComponentCode } from "../../utils/flow/replace-component-code";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";
import { updateOldComponents } from "../../utils/update-old-components";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to stop a building",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //first component

    await addComponentFromSidebar(page, {
      search: TEXTS.searchTextInput,
      testId: "input_outputText Input",
      position: { x: 50, y: 50 },
    });

    await zoomOut(page, 3);
    //second component

    await addComponentFromSidebar(page, {
      search: TEXTS.searchUrl,
      testId: "data_sourceURL",
      position: { x: 50, y: 300 },
    });

    //third component

    await addComponentFromSidebar(page, {
      search: "split text",
      testId: "processingSplit Text",
      position: { x: 300, y: 500 },
    });

    //fourth component

    await addComponentFromSidebar(page, {
      search: "data to message",
      testId: "processingData to Message",
      position: { x: 100, y: 500 },
    });

    //fifth component

    await addComponentFromSidebar(page, {
      search: TEXTS.searchChatOutput,
      testId: "input_outputChat Output",
      position: { x: 600, y: 300 },
    });

    await updateOldComponents(page);
    await removeOldApiKeys(page);

    await adjustScreenView(page, { numberOfZoomOut: 3 });

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
    await page.getByTestId("handle-parsedata-shownode-json-left").click();

    //connection 4
    await page.getByTestId("handle-parsedata-shownode-message-right").click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .click();

    await adjustScreenView(page);

    await page.getByText("Text Input", { exact: true }).click();

    await page.getByTestId("textarea_str_input_value").first().fill(",");

    await page.getByText("URL", { exact: true }).click();

    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://www.nature.com/articles/d41586-023-02870-5");

    await page.getByText("Split Text", { exact: true }).click();

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
    await adjustScreenView(page, { numberOfZoomOut: 2 });

    await page.getByTestId("title-Custom Component").first().click();

    const componentFlowRefresh = page.waitForResponse(
      (response) => {
        const url = new URL(response.url());
        return (
          response.request().method() === "GET" &&
          url.pathname === "/api/v1/flows/" &&
          url.searchParams.get("components_only") === "true" &&
          url.searchParams.get("get_all") === "true"
        );
      },
      { timeout: TIMEOUTS.standard },
    );
    await replaceComponentCode(page, timerCode);
    const refreshResponse = await componentFlowRefresh;
    expect(refreshResponse.ok()).toBeTruthy();
    expect(await refreshResponse.finished()).toBeNull();

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
