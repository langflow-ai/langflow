import { test } from "@playwright/test";
import { readFileSync } from "fs";
test.beforeEach(async ({ page }) => {
  // await page.waitForTimeout(20000);
  // test.setTimeout(120000);
});
test("chat_io_teste", async ({ page }) => {
  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  // Read your file into a buffer.
  const jsonContent = readFileSync(
    "tests/end-to-end/assets/ChatTest.json",
    "utf-8"
  );

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

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(2000);

  // Now dispatch
  await page.dispatchEvent(
    '//*[@id="react-flow-id"]/div[1]/div[1]/div',
    "drop",
    {
      dataTransfer,
    }
  );
  await page.getByLabel("fit view").click();
  await page.getByText("Run", { exact: true }).click();
  await page.getByPlaceholder("Send a message...").click();
  await page.getByPlaceholder("Send a message...").fill("teste");
  await page.getByRole("button").nth(1).click();
});
