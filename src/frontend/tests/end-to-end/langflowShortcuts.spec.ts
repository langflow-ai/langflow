import { expect, test } from "@playwright/test";
import uaParser from "ua-parser-js";

test("LangflowShortcuts", async ({ page }) => {
  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llamacpp");

  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="model_specsLlamaCpp"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("title-LlamaCpp").click();
  await page.keyboard.press(`${control}+e`);
  await page.locator('//*[@id="saveChangesBtn"]').click();

  await page.getByTestId("title-LlamaCpp").click();
  await page.keyboard.press(`${control}+d`);

  let numberOfNodes = await page.getByTestId("title-LlamaCpp").count();
  if (numberOfNodes != 2) {
    expect(false).toBeTruthy();
  }

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[1]/div/div/div[1]'
    )
    .click();
  await page.keyboard.press("Backspace");

  numberOfNodes = await page.getByTestId("title-LlamaCpp").count();
  if (numberOfNodes != 1) {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("title-LlamaCpp").click();
  await page.keyboard.press(`${control}+c`);

  await page.getByTestId("title-LlamaCpp").click();
  await page.keyboard.press(`${control}+v`);

  numberOfNodes = await page.getByTestId("title-LlamaCpp").count();
  if (numberOfNodes != 2) {
    expect(false).toBeTruthy();
  }

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[1]/div/div/div[1]'
    )
    .click();
  await page.keyboard.press("Backspace");

  await page.getByTestId("title-LlamaCpp").click();
  await page.keyboard.press(`${control}+x`);

  numberOfNodes = await page.getByTestId("title-LlamaCpp").count();
  if (numberOfNodes != 0) {
    expect(false).toBeTruthy();
  }
  await page.keyboard.press(`${control}+v`);
  numberOfNodes = await page.getByTestId("title-LlamaCpp").count();
  if (numberOfNodes != 1) {
    expect(false).toBeTruthy();
  }
});
