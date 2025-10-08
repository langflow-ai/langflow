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
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

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

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully");

    await page.getByTestId("playground-btn-flow-io").click();

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ");

    await page.getByText("Close").last().click();

    await page.getByText("Prompt", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });
    await page.getByTestId("more-options-modal").click();

    await page.getByText("Freeze", { exact: true }).first().click();

    await page.waitForSelector(".border-ring-frozen", { timeout: 3000 });

    expect(page.locator(".border-ring-frozen")).toHaveCount(1);

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

    await page.waitForTimeout(500);

    const textContents2 = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    textContents2.forEach((text) => {
      expect(text).toBe(concatAllText);
    });
  },
);
