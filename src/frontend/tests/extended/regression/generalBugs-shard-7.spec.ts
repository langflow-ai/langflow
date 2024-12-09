import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// TODO: This test might not be needed anymore
test(
  "should be able to select all with ctrl + A on advanced modal",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("ollama");
    await page.waitForSelector('[data-testid="embeddingsOllama Embeddings"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("embeddingsOllama Embeddings")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("div-generic-node").click();

    await page.keyboard.press(`ControlOrMeta+Shift+A`);

    await page.waitForSelector('[data-testid="node-modal-title"]', {
      timeout: 3000,
    });

    await page
      .getByPlaceholder("Type something...")
      .nth(2)
      .fill("ollama_test_ctrl_a_first_input");
    let value = await page
      .getByPlaceholder("Type something...")
      .nth(2)
      .inputValue();
    expect(value).toBe("ollama_test_ctrl_a_first_input");

    await page
      .getByPlaceholder("Type something...")
      .last()
      .fill("ollama_test_ctrl_a_second_input");
    let secondValue = await page
      .getByPlaceholder("Type something...")
      .last()
      .inputValue();
    expect(secondValue).toBe("ollama_test_ctrl_a_second_input");

    await page.getByPlaceholder("Type something...").last().click();

    await page.keyboard.press("ControlOrMeta+a");

    await page.keyboard.press("ControlOrMeta+c");

    await page.getByPlaceholder("Type something...").nth(2).click();

    await page.keyboard.press("ControlOrMeta+a");

    await page.keyboard.press("ControlOrMeta+v");

    value = await page
      .getByPlaceholder("Type something...")
      .nth(2)
      .inputValue();
    expect(value).toBe("ollama_test_ctrl_a_second_input");
  },
);
