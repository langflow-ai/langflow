import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.skip(
  "TextInputOutputComponent",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    // commented out because new playground does not support text io yet
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForTimeout(1000);
    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");
    await page.waitForTimeout(1000);
    await page
      .getByTestId("openaiOpenAI")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);
    let visibleElementHandle;
    const elementsTextInputOutput = await page
      .getByTestId("handle-textinput-shownode-output text-right")
      .all();
    for (const element of elementsTextInputOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }
    await visibleElementHandle.waitFor({
      state: "visible",
      timeout: 30000,
    });
    await visibleElementHandle.hover();
    await page.mouse.down();
    for (const element of elementsTextInputOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }
    await visibleElementHandle.waitFor({
      state: "visible",
      timeout: 30000,
    });
    // Move to the second element
    await visibleElementHandle.hover();
    // Release the mouse
    await page.mouse.up();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    const elementsOpenAiOutput = await page
      .getByTestId("handle-openaimodel-shownode-text-right")
      .all();
    for (const element of elementsOpenAiOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }
    await visibleElementHandle.waitFor({
      state: "visible",
      timeout: 30000,
    });
    // Click and hold on the first element
    await visibleElementHandle.hover();
    await page.mouse.down();
    const elementTextOutputInput = await page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .all();
    for (const element of elementTextOutputInput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }
    await visibleElementHandle.waitFor({
      state: "visible",
      timeout: 30000,
    });
    // Move to the second element
    await visibleElementHandle.hover();
    // Release the mouse
    await page.mouse.up();
    await page
      .getByTestId(/^rf__node-TextInput-[a-zA-Z0-9]+$/)
      .getByTestId("textarea_str_input_value")
      .fill("This is a test!");
    let outdatedComponents = await page.getByTestId("update-button").count();
    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      await page.waitForTimeout(1000);
      outdatedComponents = await page.getByTestId("update-button").count();
    }
    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      await page.waitForTimeout(1000);
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }
    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();
    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }
    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.getByTestId("button_run_text_output").click();
    await page
      .getByTestId(/^rf__node-TextOutput-[a-zA-Z0-9]+$/)
      .getByTestId("output-inspection-output message-chatoutput")
      .click();
    await page.getByText("Run Flow", { exact: true }).click();
    await page.waitForTimeout(5000);
    let textInputContent = await page
      .getByPlaceholder("Enter text...")
      .textContent();
    expect(textInputContent).toBe("This is a test!");
    await page.getByText("Outputs", { exact: true }).nth(1).click();
    await page.getByText("Text Output", { exact: true }).nth(2).click();
    let contentOutput = await page
      .getByPlaceholder("Enter text...")
      .inputValue();
    expect(contentOutput).not.toBe(null);
    await page.keyboard.press("Escape");
    await page
      .getByTestId(/^rf__node-TextInput-[a-zA-Z0-9]+$/)
      .getByTestId("textarea_str_input_value")
      .fill("This is a test, again just to be sure!");
    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.getByText("Run Flow", { exact: true }).click();
    await page.waitForTimeout(5000);
    textInputContent = await page
      .getByPlaceholder("Enter text...")
      .textContent();
    expect(textInputContent).toBe("This is a test, again just to be sure!");
    await page.getByText("Outputs", { exact: true }).nth(1).click();
    await page.getByText("Text Output", { exact: true }).nth(2).click();
    contentOutput = await page.getByPlaceholder("Enter text...").inputValue();
    expect(contentOutput).not.toBe(null);
  },
);
