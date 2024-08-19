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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();

  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("ollama");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOllama")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="react-flow-id"]/div/div[2]/button[3]').click();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTestId("generic-node-title-arrangement").click();
  await page.keyboard.press(`${control}+Shift+A`);
  await page.getByText("Close").last().click();

  await page.getByTestId("generic-node-title-arrangement").click();
  await page.keyboard.press(`${control}+d`);

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
  await page.keyboard.press(`${control}+c`);

  await page.getByTestId("title-Ollama").click();
  await page.keyboard.press(`${control}+v`);

  numberOfNodes = await page.getByTestId("title-Ollama")?.count();
  if (numberOfNodes != 2) {
    expect(false).toBeTruthy();
  }

  await ollamaTitleElement.click();
  await page.keyboard.press("Backspace");

  await page.getByTestId("title-Ollama").click();
  await page.keyboard.press(`${control}+x`);

  numberOfNodes = await page.getByTestId("title-Ollama")?.count();
  if (numberOfNodes != 0) {
    expect(false).toBeTruthy();
  }
  await page.keyboard.press(`${control}+v`);
  numberOfNodes = await page.getByTestId("title-Ollama")?.count();
  if (numberOfNodes != 1) {
    expect(false).toBeTruthy();
  }
});
