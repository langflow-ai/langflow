import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { replaceComponentCode } from "../../utils/flow/replace-component-code";

const SLEEP_60_CUSTOM_COMPONENT = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from time import sleep
from langflow.schema.message import Message

class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "custom_components"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Message:
        data = Data(value=self.input_value)
        self.status = data
        sleep(60)
        return data`;

test(
  "User must be able to stop building from inside Playground",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await page.waitForSelector(
      `[data-testid="${TID.sidebarCustomComponentButton}"]`,
      { timeout: TIMEOUTS.short },
    );

    await page.waitForSelector(
      `[data-testid="${TID.canvasControlsDropdown}"]`,
      {
        timeout: TIMEOUTS.short,
      },
    );

    await page.getByTestId(TID.sidebarCustomComponentButton).click();
    await adjustScreenView(page);

    await addComponentFromSidebar(page, {
      search: "chat output",
      testId: "input_outputChat Output",
      position: { x: 400, y: 400 },
    });

    await adjustScreenView(page);

    await page.getByTestId(TID.divGenericNode).nth(1).click();
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("expand-button-modal").click();

    await page.getByTestId(TID.divGenericNode).nth(0).click();

    await replaceComponentCode(page, SLEEP_60_CUSTOM_COMPONENT);
    await adjustScreenView(page, { numberOfZoomOut: 2 });

    // Connect Custom Component output → Chat Output input
    const elementCustomComponentOutput = await page
      .getByTestId("handle-customcomponent-shownode-output-right")
      .first();

    await elementCustomComponentOutput.hover();
    await page.mouse.down();
    const elementChatOutput = await page
      .getByTestId("handle-chatoutput-shownode-inputs-left")
      .first();
    await elementChatOutput.hover();
    await page.mouse.up();

    await page.waitForSelector(`[data-testid="${TID.buttonRunChatOutput}"]`, {
      timeout: TIMEOUTS.short,
    });

    await page.getByTestId(TID.buttonRunChatOutput).click();

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector(`[data-testid="${TID.buttonStop}"]`, {
      timeout: TIMEOUTS.standard,
    });

    const elements = await page.$$(`[data-testid="${TID.buttonStop}"]`);
    if (elements.length > 0) {
      const lastElement = elements[elements.length - 1];
      await lastElement.waitForElementState("visible");
    }

    await expect(page.getByTestId(TID.buttonStop).last()).toBeVisible();
    await page.getByTestId(TID.buttonStop).last().click();

    await page.waitForSelector("text=build stopped", {
      timeout: TIMEOUTS.standard,
    });
    await expect(page.getByText("build stopped")).toBeVisible();
  },
);
