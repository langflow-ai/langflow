import { expect, test } from "@playwright/test";

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

test("should order the visualization", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.waitForTimeout(2000);
  await page.getByText("Alphabetical").click();

  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.getByText("Popular").click();

  await page.getByText("Basic RAG").isVisible();
});

test("should filter by type", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Website Content QA").isVisible();

  await page.getByTestId("flows-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroup = await page.getByTestId("icon-Group")?.count();
  expect(iconGroup).not.toBe(0);

  await page.getByText("icon-ToyBrick").last().isHidden();

  await page.getByTestId("components-button-store").click();
  await page.waitForTimeout(8000);

  await page.getByTestId("icon-Group").last().isHidden();
  let toyBrick = await page.getByTestId("icon-ToyBrick")?.count();
  expect(toyBrick).not.toBe(0);

  await page.getByTestId("all-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroupAllCount = await page.getByTestId("icon-Group")?.count();
  await page.waitForTimeout(2000);
  let toyBrickAllCount = await page.getByTestId("icon-ToyBrick")?.count();
  await page.waitForTimeout(2000);

  if (iconGroupAllCount === 0 || toyBrickAllCount === 0) {
    expect(false).toBe(true);
  }
});
