import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";

test(
  "user must be able to edit an empty prompt",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    let outdatedComponents = await page.getByTestId("update-button").count();

    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    await page.getByTestId("button_open_prompt_modal").click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText(TEXTS.editPrompt, { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST");

    await page.getByText(TEXTS.editPrompt, { exact: true }).click();

    let promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .last()
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST");

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText(TEXTS.editPrompt, { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").last().click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST 2");

    await page.getByText(TEXTS.editPrompt, { exact: true }).click();

    promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .last()
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST 2");
  },
);
