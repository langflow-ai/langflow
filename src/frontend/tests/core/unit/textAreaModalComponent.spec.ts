import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "TextAreaModalComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page.waitForSelector('[data-testid="processingPrompt Template"]', {
      timeout: 30000,
    });

    await page
      .locator('//*[@id="processingPrompt Template"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    await page.getByTestId("promptarea_prompt_template").click();

    await page.getByTestId("modal-promptarea_prompt_template").fill("{text}");

    const valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
    if (valueBadgeOne != "text") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("genericModalBtnSave").click();

    await page
      .getByTestId("textarea_str_text")
      .fill(
        "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!",
      );

    // Test cursor position preservation
    const textInput = page.getByTestId("textarea_str_text");
    await textInput.click();
    await textInput.press("Home"); // Move cursor to start
    await textInput.press("ArrowRight"); // Move cursor to position 1
    await textInput.press("ArrowRight"); // Move cursor to position 2
    await textInput.pressSequentially("Y", { delay: 100 }); // Type at position 2
    const cursorValue = await textInput.inputValue();
    if (!cursorValue.startsWith("teY")) {
      expect(false).toBeTruthy();
    }
    await textInput.fill(
      "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!",
    );

    await page
      .getByTestId("button_open_text_area_modal_textarea_str_text")
      .click();

    await page.waitForSelector('[data-testid="icon-FileText"]', {
      timeout: 3000,
    });

    const value = await page.getByTestId("text-area-modal").inputValue();

    if (
      value !=
      "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!"
    ) {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("text-area-modal").fill("test123123");

    await page.getByTestId("genericModalBtnSave").click();

    const valueTextArea = await page
      .getByTestId("textarea_str_text")
      .inputValue();

    if (valueTextArea != "test123123") {
      expect(false).toBeTruthy();
    }
  },
);
