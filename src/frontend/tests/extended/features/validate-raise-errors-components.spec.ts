import { expect, test } from "@playwright/test";
import { addCustomComponent } from "../../utils/add-custom-component";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to see errors on popups when raise an error",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const customComponentCodeWithRaiseErrorMessage = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data


class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            info="This is a custom component Input",
            value="Hello, World!",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        msg = "THIS IS A TEST ERROR MESSAGE"
        raise ValueError(msg)
        data = Data(value=self.input_value)
        self.status = data
        return data
    `;

    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 3000,
      },
    );

    await addCustomComponent(page);

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    await page.waitForTimeout(1000);

    await page.waitForSelector('[data-testid="title-Custom Component"]', {
      timeout: 3000,
    });
    await page.getByTestId("title-Custom Component").click();

    await page.getByTestId("code-button-modal").click();

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page
      .locator("textarea")
      .fill(customComponentCodeWithRaiseErrorMessage);

    await page.getByText("Check & Save").last().click();

    await page.getByTestId("button_run_custom component").click();

    await page.waitForSelector("text=THIS IS A TEST ERROR MESSAGE", {
      timeout: 3000,
    });

    const numberOfErrorMessages = await page
      .getByText("THIS IS A TEST ERROR MESSAGE")
      .count();

    expect(numberOfErrorMessages).toBeGreaterThan(0);
  },
);
