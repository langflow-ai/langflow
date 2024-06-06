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
    "utf-8",
  );

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(2000);

  // Create the DataTransfer and File
  const dataTransfer = await page.evaluateHandle((data) => {
    const dt = new DataTransfer();
    // Convert the buffer to a hex array
    const file = new File([data], "ChatTest.json", {
      type: "application/json",
    });
    dt.items.add(file);
    return dt;
  }, jsonContent);

  // Now dispatch
  await page.dispatchEvent(
    '//*[@id="react-flow-id"]/div[1]/div[1]/div',
    "drop",
    {
      dataTransfer,
    },
  );
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
