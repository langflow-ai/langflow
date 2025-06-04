import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "User must be able to stop building from inside Playground",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 3000,
      },
    );

    await page.waitForSelector('[data-testid="zoom_out"]', {
      timeout: 3000,
    });

    await page.getByTestId("sidebar-custom-component-button").click();
    await page.getByTitle("fit view").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.waitForTimeout(500);
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 400 },
      });

    await adjustScreenView(page);

    await page.getByTestId("div-generic-node").nth(1).click();

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    await page.getByTestId("div-generic-node").nth(0).click();

    await page.getByTestId("code-button-modal").nth(0).click();

    const waitTimeoutCode = `
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

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page.locator("textarea").fill(waitTimeoutCode);

    await page.getByText("Check & Save").last().click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    //connection 1
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

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="button-stop"]', {
      timeout: 30000,
    });

    const elements = await page.$$('[data-testid="button-stop"]');

    if (elements.length > 0) {
      const lastElement = elements[elements.length - 1];
      await lastElement.waitForElementState("visible");
    }

    expect(await page.getByTestId("button-stop").last()).toBeVisible();

    await page.getByTestId("button-stop").last().click();

    await page.waitForSelector("text=build stopped", { timeout: 30000 });
    expect(await page.getByText("build stopped").isVisible()).toBeTruthy();
  },
);
