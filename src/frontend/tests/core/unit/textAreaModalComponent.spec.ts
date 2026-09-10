import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";

test.beforeEach(async ({ page }, testInfo) => {
  await routeTestScopedDefaultFlowNames(page, testInfo, "text-area-modal");
});

test(
  "TextAreaModalComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    const promptTemplate = "{text}";
    const textValue =
      "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!";

    await addComponentFromSidebar(page, {
      search: TEXTS.searchPrompt,
      testId: "models_and_agentsPrompt Template",
    });
    await adjustScreenView(page);

    await page.getByTestId("button_open_prompt_modal").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(promptTemplate);
    await expect(page.locator("#badge0")).toHaveText("text");

    const promptValidationResponsePromise = page.waitForResponse((response) => {
      const request = response.request();
      if (
        request.method() !== "POST" ||
        !response.url().endsWith("/api/v1/validate/prompt")
      ) {
        return false;
      }

      const body = request.postDataJSON() as { template?: unknown };
      return body.template === promptTemplate;
    });
    await page.getByTestId("genericModalBtnSave").click();
    const promptValidationResponse = await promptValidationResponsePromise;
    expect(promptValidationResponse.status()).toBe(200);
    await expect(
      page.getByTestId("modal-promptarea_prompt_template"),
    ).toBeHidden();

    const textInput = page.getByTestId("textarea_str_text");
    await expect(textInput).toBeVisible();
    await textInput.fill(textValue);

    // Test cursor position preservation
    await textInput.click();
    await textInput.press("Home"); // Move cursor to start
    await textInput.press("ArrowRight"); // Move cursor to position 1
    await textInput.press("ArrowRight"); // Move cursor to position 2
    await textInput.pressSequentially("Y", { delay: 100 }); // Type at position 2
    await expect(textInput).toHaveValue(/^teY/);
    await textInput.fill(textValue);
    await expect(textInput).toHaveValue(textValue);

    await page
      .getByTestId("button_open_text_area_modal_textarea_str_text")
      .click();

    await page.waitForSelector('[data-testid="icon-FileText"]', {
      timeout: 3000,
    });

    await expect(page.getByTestId("text-area-modal")).toHaveValue(textValue);

    await page.getByTestId("text-area-modal").fill("test123123");

    await page.getByTestId("genericModalBtnSave").click();

    await expect(textInput).toHaveValue("test123123");
  },
);
