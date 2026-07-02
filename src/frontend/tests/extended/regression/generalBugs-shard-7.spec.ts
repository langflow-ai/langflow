import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";

import { openBlankFlow } from "../../utils/flow/open-blank-flow";

// TODO: This test might not be needed anymore
test(
  "should be able to select all with ctrl + A on advanced modal",
  { tag: ["@release"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("data_sourceURL")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-url").click();
      });
    await adjustScreenView(page, { numberOfZoomOut: 3 });

    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 5000,
      state: "visible",
    });

    await page.getByTestId("div-generic-node").click();

    await page.keyboard.press(`ControlOrMeta+Shift+A`);

    await page.waitForTimeout(500);

    // Wait for the modal inputs to be visible
    const urlInput = page.getByTestId("inputlist_str_urls_0");
    await expect(urlInput).toBeVisible({ timeout: 5000 });

    // Fill the first input.
    await urlInput.fill("url_test_ctrl_a_first_input");
    let value = await urlInput.inputValue();
    expect(value).toBe("url_test_ctrl_a_first_input");

    await page.keyboard.press("ControlOrMeta+a");

    await page.keyboard.press("ControlOrMeta+c");

    await page.keyboard.press("Backspace");
    value = await urlInput.inputValue();
    expect(value).toBe("");

    await page.keyboard.press("ControlOrMeta+v");

    value = await urlInput.inputValue();
    expect(value).toBe("url_test_ctrl_a_first_input");
  },
);
