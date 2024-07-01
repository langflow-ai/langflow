import { test } from "@playwright/test";

test("should add API-KEY", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click();
  await page
    .getByPlaceholder("Insert your API Key")
    .fill("testtesttesttesttesttest");

  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();
});

test("should delete a flow", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  await page.waitForSelector("text=Store", { timeout: 30000 });

  await page.getByText("Store").nth(0).click();

  await page.waitForSelector('[data-testid="install-Website Content QA"]', {
    timeout: 100000,
  });

  await page.getByTestId("install-Website Content QA").click();

  await page.waitForSelector("text=My Collection", { timeout: 30000 });

  await page.getByText("My Collection").nth(0).click();

  await page.waitForSelector("text=Website Content QA", { timeout: 30000 });

  await page.getByText("Website Content QA").first().isVisible();

  await page.waitForSelector('[data-testid="checkbox-component"]', {
    timeout: 100000,
  });

  await page.getByTestId("checkbox-component").first().click();

  await page.getByTestId("icon-Trash2").click();
  await page
    .getByText("Are you sure you want to delete the selected component?")
    .isVisible();
  await page.getByText("Delete").nth(1).click();
  await page.waitForTimeout(1000);
  await page.getByText("Successfully").first().isVisible();
});

test("should delete a component", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByText("Store").nth(0).click();
  await page.getByTestId("install-Basic RAG").click();
  await page.waitForTimeout(5000);
  await page.getByText("My Collection").nth(0).click();
  await page.getByText("Components").first().click();
  await page.getByText("Basic RAG").first().isVisible();

  await page.waitForSelector('[data-testid="checkbox-component"]', {
    timeout: 100000,
  });

  await page.getByTestId("checkbox-component").first().click();

  await page.getByTestId("icon-Trash2").click();
  await page
    .getByText("Are you sure you want to delete the selected component?")
    .isVisible();
  await page.getByText("Delete").nth(1).click();
  await page.waitForTimeout(1000);
  await page.getByText("Successfully").first().isVisible();
});
