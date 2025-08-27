import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should be able to see error when something goes wrong on Code Modal",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 30000,
      },
    );

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("div-generic-node").click();
    await page.getByTestId("code-button-modal").click();

    const customCodeWithError = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import pytorch

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

    def build_output(self) -> Data:
        data = Data(value=self.input_value)
        self.status = data
        return data
  `;

    await page.locator("textarea").press("Control+a");
    await page.locator("textarea").fill(customCodeWithError);

    await page.getByText("Check & Save").last().click();

    // Wait for the error message to appear and have sufficient length
    await page.waitForFunction(
      () => {
        const errorElement = document.querySelector(
          '[data-testid="title_error_code_modal"]',
        );
        return (
          errorElement &&
          errorElement.textContent &&
          errorElement.textContent.length > 20
        );
      },
      { timeout: 10000 }, // 5 second timeout
    );

    const error = await page
      .getByTestId("title_error_code_modal")
      .textContent();

    expect(error!.length).toBeGreaterThan(20);
  },
);
