import { expect, test } from "@playwright/test";
import uaParser from "ua-parser-js";

test("User must be able to stop building from inside Playground", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-custom-component-button").click();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

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
    documentation: str = "http://docs.langflow.org/components/custom"
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

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

  await page.locator(".ace_content").click();
  await page.keyboard.press(`${control}+A`);
  await page.locator("textarea").fill(waitTimeoutCode);

  await page.getByText("Check & Save").last().click();

  await page.waitForTimeout(1000);

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
    .getByTestId("handle-chatoutput-shownode-text-left")
    .first();
  await elementChatOutput.hover();
  await page.mouse.up();

  await page.waitForTimeout(1000);

  await page.getByTestId("button_run_chat output").click();

  await page.waitForTimeout(1000);

  await page.getByText("Playground", { exact: true }).last().click();

  await page.waitForTimeout(1000);

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
});
