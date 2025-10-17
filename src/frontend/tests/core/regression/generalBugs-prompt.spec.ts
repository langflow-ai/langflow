import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to edit an empty prompt",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    let outdatedComponents = await page.getByTestId("update-button").count();

    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    await page.getByTestId("promptarea_prompt_template").click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText("Edit Prompt", { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST");

    await page.getByText("Edit Prompt", { exact: true }).click();

    let promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .last()
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST");

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText("Edit Prompt", { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST 2");

    await page.getByText("Edit Prompt", { exact: true }).click();

    promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .last()
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST 2");
  },
);
