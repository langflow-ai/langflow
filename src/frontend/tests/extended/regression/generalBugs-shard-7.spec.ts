import { expect, test } from "@playwright/test";
import uaParser from "ua-parser-js";

// TODO: This test might not be needed anymore
test("should be able to select all with ctrl + A on advanced modal", async ({
  page,
}) => {
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

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("ollama");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("embeddingsOllama Embeddings")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

  await page.getByTestId("div-generic-node").click();

  await page.keyboard.press(`${control}+Shift+A`);

  await page.waitForTimeout(1000);

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
  await page.waitForTimeout(1000);

  await page.keyboard.down(control);
  await page.waitForTimeout(200);
  await page.keyboard.press("a");
  await page.keyboard.up(control);

  await page.waitForTimeout(1000);

  await page.keyboard.down(control);
  await page.waitForTimeout(200);
  await page.keyboard.press("c");
  await page.keyboard.up(control);

  await page.waitForTimeout(1000);

  await page.getByPlaceholder("Type something...").nth(2).click();

  await page.waitForTimeout(1000);

  await page.keyboard.down(control);
  await page.waitForTimeout(200);
  await page.keyboard.press("a");
  await page.keyboard.up(control);

  await page.waitForTimeout(1000);

  await page.keyboard.down(control);
  await page.waitForTimeout(200);
  await page.keyboard.press("v");
  await page.keyboard.up(control);

  value = await page.getByPlaceholder("Type something...").nth(2).inputValue();
  expect(value).toBe("ollama_test_ctrl_a_second_input");
});
