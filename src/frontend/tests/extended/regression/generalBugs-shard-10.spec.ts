import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "freeze must work correctly",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    const promptText = "answer as you are a dog";
    const newPromptText = "answer as you are a bird";

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    await page.getByText(TEXTS.componentLanguageModel).last().click();
    await page.keyboard.press("Delete");

    //connection 1

    await page
      .getByTestId("handle-prompt-shownode-prompt-right")
      .first()
      .click();

    await adjustScreenView(page);

    await page
      .getByTestId("handle-chatoutput-shownode-inputs-left")
      .first()
      .click();

    await page.getByText("Prompt Template", { exact: true }).last().click();

    await page.getByTestId("button_open_prompt_modal").click();

    await page.getByTestId("modal-promptarea_prompt_template").fill(promptText);

    await page.getByText(TEXTS.checkAndSave).click();

    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`);

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

    // await page.getByText(TEXTS.close).last().click();
    await page.getByTestId("playground-close-button").click();

    // Freeze the Chat Output node (not Prompt) so the entire response is cached
    await page.getByText("Chat Output", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Freeze", { exact: true }).first().click();

    await page.waitForSelector(".border-ring-frozen", { timeout: 3000 });

    expect(page.locator(".border-ring-frozen")).toHaveCount(1);

    await page.getByText("Prompt Template", { exact: true }).last().click();

    // Now change the prompt (this should have no effect since Chat Output is frozen)
    await page.getByTestId("button_open_prompt_modal").click();

    await page.waitForTimeout(500);

    if ((await page.getByTestId("edit-prompt-sanitized").count()) > 0) {
      await page.getByTestId("edit-prompt-sanitized").last().click();
    }

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(newPromptText);

    await page.getByText(TEXTS.checkAndSave).click();

    await page.waitForTimeout(500);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

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
