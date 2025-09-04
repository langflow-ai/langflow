import { expect, test } from "@playwright/test";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "CodeAreaModalComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 3000,
    });

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("canvas_controls_dropdown").click();

    await page.waitForSelector('[data-testid="zoom_out"]', {
      timeout: 3000,
    });
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("sidebar-custom-component-button").click();

    await expect(page.getByTestId("code-button-modal")).toBeVisible({
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").last().click();

    const codeInputCode = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import CodeInput, Output
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
        CodeInput(
            name="function_code",
            display_name="Function Code",
            info="The code for the function.",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Message:
        data = Data(value=self.function_code)
        self.status = data
        sleep(60)
        return data`;

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page.locator("textarea").fill(codeInputCode);

    await page.getByText("Check & Save").last().click();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("codearea_code_function_code").click();

    const wCode =
      'def python_function(text: str) -> st:    """This is a default python function that returns the input text"""    return text';

    const customComponentCode = `from typing import Callable
from langflow.field_typing import Code
from langflow.interface.custom.custom_component import CustomComponent
from langflow.interface.custom.utils import get_function

class PythonFunctionComponent(CustomComponent):
    def python_function(text: str) -> str:
        """This is a default python function that returns the input text"""
        return text`;

    await page.locator(".ace_content").click();
    await page.locator("textarea").press("ControlOrMeta+a");
    await page.locator("textarea").fill(wCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();
    await expect(
      page.getByText("invalid syntax (<unknown>, line 1)"),
    ).toBeVisible({ timeout: 3000 });
    await page.locator("textarea").press("ControlOrMeta+a");
    await page.locator("textarea").fill(customComponentCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();
    await expect(page.getByTestId("codearea_code_function_code")).toHaveText(
      customComponentCode,
      { timeout: 3000 },
    );
  },
);
