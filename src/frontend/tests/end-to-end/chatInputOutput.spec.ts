import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";

test("chat_io_teste", async ({ page }) => {
  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  await page.waitForTimeout(2000);

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

  const jsonContent = readFileSync(
    "src/frontend/tests/end-to-end/assets/ChatTest.json",
    "utf-8"
  );

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat output");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  // Click and hold on the first element
  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div[8]/button/div/div'
    )
    .hover();
  await page.mouse.down();

  // Move to the second element
  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div[3]/div/button/div/div'
    )
    .hover();

  // Release the mouse
  await page.mouse.up();

  await page.getByLabel("fit view").click();
  await page.getByText("Playground", { exact: true }).click();
  await page.getByPlaceholder("Send a message...").click();
  await page.getByPlaceholder("Send a message...").fill("teste");
  await page.getByRole("button").nth(1).click();
  const chat_output = page.getByTestId("chat-message-AI-teste");
  const chat_input = page.getByTestId("chat-message-User-teste");
  await expect(chat_output).toHaveText("teste");
  await expect(chat_input).toHaveText("teste");
});
