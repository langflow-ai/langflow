import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "freeze must work correctly",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    const promptText = "answer as you are a dog";
    const newPromptText = "answer as you are a bird";

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 3000,
    });

    await page.getByTestId("fit_view").click();

    await page.getByText("openai").first().click();
    await page.keyboard.press("Delete");

    //connection 1

    const elementPrompt = await page
      .getByTestId("handle-prompt-shownode-prompt message-right")
      .first();
    await elementPrompt.hover();
    await page.mouse.down();

    await page.locator('//*[@id="react-flow-id"]').hover();

    const elementChatOutput = await page
      .getByTestId("handle-chatoutput-shownode-text-left")
      .first();
    await elementChatOutput.hover();
    await page.mouse.up();

    await page.locator('//*[@id="react-flow-id"]').hover();

    await page.getByTestId("button_open_prompt_modal").click();

    await page.getByTestId("modal-promptarea_prompt_template").fill(promptText);

    await page.getByText("Check & Save").click();

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("playground-btn-flow-io").click();

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ");

    await page.getByText("Close").last().click();

    await page.getByText("Prompt", { exact: true }).click();
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Freeze", { exact: true }).last().click();

    await page.locator('//*[@id="react-flow-id"]').click();

    expect(page.getByTestId("icon-Snowflake").first()).toBeVisible();

    await page.locator('//*[@id="react-flow-id"]').click();

    await page.getByTestId("button_open_prompt_modal").click();

    await page.getByTestId("edit-prompt-sanitized").first().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(newPromptText);

    await page.getByText("Check & Save").click();

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("playground-btn-flow-io").click();

    const textContents2 = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText2 = textContents2.join(" ");

    expect(concatAllText2).toBe(concatAllText);
  },
);
