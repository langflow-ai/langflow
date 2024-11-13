import { expect, test } from "@playwright/test";
import uaParser from "ua-parser-js";
test("LangflowShortcuts", async ({ page }) => {
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
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("ollama");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOllama")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="react-flow-id"]/div/div[2]/button[3]').click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
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
});
