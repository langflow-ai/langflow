import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

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
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    await page.getByText("openai").last().click();
    await page.keyboard.press("Delete");

    //connection 1

    await page
      .getByTestId("handle-prompt-shownode-prompt-right")
      .first()
      .click();

    await page
      .getByTestId("handle-chatoutput-shownode-inputs-left")
      .first()
      .click();

    await page.getByTestId("button_open_prompt_modal").click();

    await page.getByTestId("modal-promptarea_prompt_template").fill(promptText);

    await page.getByText("Check & Save").click();

    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully");

    await page.getByTestId("playground-btn-flow-io").click();

    // Wait for chat messages to be fully loaded/streamed
    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });
    // Wait for streaming to complete
    await page.waitForTimeout(1000);

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    // Get the first response
    const firstResponseText = textContents[textContents.length - 1];

    // Ensure we captured a non-empty response
    expect(firstResponseText.length).toBeGreaterThan(0);

    await page.getByText("Close").last().click();

    // Freeze the Chat Output node (not Prompt) so the entire response is cached
    await page.getByText("Chat Output", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Freeze", { exact: true }).first().click();

    await page.waitForSelector(".border-ring-frozen", { timeout: 3000 });

    expect(page.locator(".border-ring-frozen")).toHaveCount(1);

    // Now change the prompt (this should have no effect since Chat Output is frozen)
    await page.getByTestId("button_open_prompt_modal").click();

    await page.waitForTimeout(500);

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(newPromptText);

    await page.getByText("Check & Save").click();

    await page.waitForTimeout(500);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("playground-btn-flow-io").click();

    // Wait for chat messages to be fully loaded/streamed
    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });
    // Wait for streaming to complete
    await page.waitForTimeout(1000);

    const textContents2 = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    // The frozen node should return the same cached output
    textContents2.forEach((text) => {
      expect(text).toBe(firstResponseText);
    });
  },
);
