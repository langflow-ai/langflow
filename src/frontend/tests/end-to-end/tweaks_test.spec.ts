import { expect, test } from "@playwright/test";

test("curl_api_generation", async ({ page, context }) => {
  await page.goto("/");
  await page.locator('//*[@id="new-project-btn"]').click();
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("heading", { name: "Data Ingestion" }).click();
  await page.waitForTimeout(2000);
  await page.getByText("API", { exact: true }).click();
  await page.getByRole("tab", { name: "cURL" }).click();
  await page.getByRole("button", { name: "Copy Code" }).click();
  const handle = await page.evaluateHandle(() =>
    navigator.clipboard.readText()
  );
  const clipboardContent = await handle.jsonValue();
  const oldValue = clipboardContent;
  expect(clipboardContent.length).toBeGreaterThan(0);
  await page.getByRole("tab", { name: "Tweaks" }).click();
  await page
    .getByRole("heading", { name: "URL" })
    .locator("div")
    .first()
    .click();
  await page.getByRole("textbox", { name: "Type something..." }).click();
  await page
    .getByRole("textbox", { name: "Type something..." })
    .press("Control+a");
  await page.getByRole("textbox", { name: "Type something..." }).fill("teste");
  await page.getByRole("tab", { name: "cURL" }).click();
  await page.getByRole("button", { name: "Copy Code" }).click();
  const handle2 = await page.evaluateHandle(() =>
    navigator.clipboard.readText()
  );
  const clipboardContent2 = await handle2.jsonValue();
  const newValue = clipboardContent2;
  expect(oldValue).not.toBe(newValue);
  expect(clipboardContent2.length).toBeGreaterThan(clipboardContent.length);
});
