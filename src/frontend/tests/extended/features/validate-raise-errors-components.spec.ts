import { expect, test } from "../../fixtures";
import { addCustomComponent } from "../../utils/add-custom-component";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

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
    await openBlankFlow(page);

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 30000,
      },
    );

    await addCustomComponent(page);
    await adjustScreenView(page, { numberOfZoomOut: 1 });

    await page.waitForTimeout(1000);

    await page.waitForSelector('[data-testid="title-Custom Component"]', {
      timeout: 10000,
    });
    await page.getByTestId("title-Custom Component").click();

    await page.getByTestId("code-button-modal").last().click();

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page
      .locator("textarea")
      .fill(customComponentCodeWithRaiseErrorMessage);

    await page.getByText(TEXTS.checkAndSave).last().click();

    await page.getByTestId("button_run_custom component").click();

    // Building and running a custom component that raises a runtime error can
    // take well over 3s on slower (e.g. Windows) CI runners, so give the error
    // popup the same generous window used by other build-dependent assertions.
    await page.waitForSelector("text=THIS IS A TEST ERROR MESSAGE", {
      timeout: 30000,
    });

    const numberOfErrorMessages = await page
      .getByText("THIS IS A TEST ERROR MESSAGE")
      .count();

    expect(numberOfErrorMessages).toBeGreaterThan(0);
  },
);
