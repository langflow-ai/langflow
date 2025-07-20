import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "LangflowShortcuts",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("ollama");

    await page.waitForSelector('[data-testid="ollamaOllama"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("ollamaOllama")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();

    await adjustScreenView(page);
    await page.getByTestId("generic-node-title-arrangement").click();
    await page.keyboard.press(`ControlOrMeta+Shift+A`);
    await page.getByText("Close").last().click();

    await page.getByTestId("generic-node-title-arrangement").click();
    await page.keyboard.press(`ControlOrMeta+d`);

    let numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    if (numberOfNodes != 2) {
      expect(false).toBeTruthy();
    }

    const ollamaTitleElement = await page.getByTestId("title-Ollama").last();

    await ollamaTitleElement.click();
    await page.keyboard.press("Backspace");

    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    if (numberOfNodes != 1) {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("generic-node-title-arrangement").click();
    await page.keyboard.press(`ControlOrMeta+c`);

    await page.getByTestId("title-Ollama").click();
    await page.keyboard.press(`ControlOrMeta+v`);

    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    if (numberOfNodes != 2) {
      expect(false).toBeTruthy();
    }

    await ollamaTitleElement.click();
    await page.keyboard.press("Backspace");

    await page.getByTestId("title-Ollama").click();
    await page.keyboard.press(`ControlOrMeta+x`);

    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    if (numberOfNodes != 0) {
      expect(false).toBeTruthy();
    }
    await page.keyboard.press(`ControlOrMeta+v`);
    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    if (numberOfNodes != 1) {
      expect(false).toBeTruthy();
    }

    // Test undo (Command+Z or Control+Z)
    await page.getByTestId("title-Ollama").click();
    await page.keyboard.press("Backspace");
    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    expect(numberOfNodes).toBe(0);

    await page.keyboard.press(`ControlOrMeta+z`);
    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    expect(numberOfNodes).toBe(1);

    // Test redo (Command+Y or Control+Y)
    await page.keyboard.press(`ControlOrMeta+y`);
    numberOfNodes = await page.getByTestId("title-Ollama")?.count();
    expect(numberOfNodes).toBe(0);
  },
);
