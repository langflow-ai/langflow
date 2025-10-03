import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to use a component with undefined replacement",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTestId("title-Custom Component").click();

    await page.getByTestId("code-button-modal").last().click();

    const problematicCode = `
# from lfx.field_typing import Data
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data


class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "CustomComponent"
    replacement = ["knowledgebases.KnowledgeRetrieval", "knowledgebases.KnowledgeIngestion", "THISISNOTEXISTING.COMPONENT"]  # This line was causing the crash
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
        data = Data(value=self.input_value)
        self.status = data
        return data

    `;

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page.locator("textarea").fill(problematicCode);

    await page.getByText("Check & Save").last().click();

    await page.waitForTimeout(1000);
    await page.waitForSelector("text=No direct replacement", {
      timeout: 30000,
    });

    const numberOfDirectReplacementText = await page
      .getByText("No direct replacement")
      .count();
    expect(numberOfDirectReplacementText).toBe(1);
  },
);
