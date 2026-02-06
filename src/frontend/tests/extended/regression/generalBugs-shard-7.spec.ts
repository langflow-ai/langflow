import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { zoomOut } from "../../utils/zoom-out";

// TODO: This test might not be needed anymore
test(
  "should be able to select all with ctrl + A on advanced modal",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 10000,
    });

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("ollama");
    await page.waitForSelector('[data-testid="ollamaOllama Embeddings"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("ollamaOllama Embeddings")
      .hover()
      .then(async () => {
        await page
          .getByTestId("add-component-button-ollama-embeddings")
          .click();
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
    await expect(
      page.getByTestId(/^popover-anchor-input-base_url.*/).nth(0),
    ).toBeVisible({ timeout: 5000 });

    // Fill the first input (base_url field)
    await page
      .getByTestId(/^popover-anchor-input-base_url.*/)
      .nth(0)
      .fill("ollama_test_ctrl_a_first_input");
    let value = await page
      .getByTestId(/^popover-anchor-input-base_url.*/)
      .nth(0)
      .inputValue();
    expect(value).toBe("ollama_test_ctrl_a_first_input");

    await page.keyboard.press("ControlOrMeta+a");

    await page.keyboard.press("ControlOrMeta+c");

    await page.keyboard.press("Backspace");
    value = await page
      .getByTestId(/^popover-anchor-input-base_url.*/)
      .nth(0)
      .inputValue();
    expect(value).toBe("");

    await page.keyboard.press("ControlOrMeta+v");

    value = await page
      .getByTestId(/^popover-anchor-input-base_url.*/)
      .nth(0)
      .inputValue();
    expect(value).toBe("ollama_test_ctrl_a_first_input");
  },
);
