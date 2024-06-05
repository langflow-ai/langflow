import { test } from "@playwright/test";

test("shoud delete a flow", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByText("Store").nth(0).click();

  await page.getByText("API Key", { exact: true }).click();
  await page
    .getByPlaceholder("Insert your API Key", { exact: true })
    .fill(process.env.STORE_API_KEY ?? "");
  await page.getByText("Save").last().click();
  await page.waitForTimeout(8000);
  await page.getByText("Store").nth(0).click();

  await page.getByTestId("install-Website Content QA").click();
  await page.waitForTimeout(5000);
  await page.getByText("My Collection").nth(0).click();
  await page.getByText("Website Content QA").first().isVisible();
  await page.getByLabel("checkbox-component").first().click();
  await page.getByTestId("icon-Trash2").click();
  await page
    .getByText("Are you sure you want to delete the selected component?")
    .isVisible();
  await page.getByText("Delete").nth(1).click();
  await page.waitForTimeout(1000);
  await page.getByText("Successfully").first().isVisible();
});

test("shoud delete a component", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByText("Store").nth(0).click();
  await page.getByTestId("install-Basic RAG").click();
  await page.waitForTimeout(5000);
  await page.getByText("My Collection").nth(0).click();
  await page.getByText("Components").first().click();
  await page.getByText("Basic RAG").first().isVisible();
  await page.getByLabel("checkbox-component").first().click();
  await page.getByTestId("icon-Trash2").click();
  await page
    .getByText("Are you sure you want to delete the selected component?")
    .isVisible();
  await page.getByText("Delete").nth(1).click();
  await page.waitForTimeout(1000);
  await page.getByText("Successfully").first().isVisible();
});
