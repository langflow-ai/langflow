import { expect, test } from "@playwright/test";

test(
  "TextAreaModalComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");

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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page.waitForSelector('[data-testid="promptsPrompt"]', {
      timeout: 30000,
    });

    await page
      .locator('//*[@id="promptsPrompt"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("promptarea_prompt_template").click();

    await page.getByTestId("modal-promptarea_prompt_template").fill("{text}");

    let valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
    if (valueBadgeOne != "text") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("genericModalBtnSave").click();

    await page
      .getByTestId("textarea_str_text")
      .fill(
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
