import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should use webhook component on API", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );
  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }
  await page.goto("/");
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

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("webhook");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("dataWebhook Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.waitForTimeout(2000);
  await page.getByText("API", { exact: true }).click();

  await page.getByText("Webhook cURL", { exact: true }).click();
  await page.getByRole("tab", { name: "Webhook cURL" }).click();

  await page.getByTestId("icon-Copy").last().click();

  const handle = await page.evaluateHandle(() =>
    navigator.clipboard.readText(),
  );
  const clipboardContent = await handle.jsonValue();
  expect(clipboardContent.length).toBeGreaterThan(0);
  expect(clipboardContent).toContain("curl -X POST");
  expect(clipboardContent).toContain("webhook");
  await page.getByRole("tab", { name: "Tweaks" }).click();
  // await page.getByText("Webhook Input").isVisible();
  // await page.getByText("Webhook Input").click();
});
