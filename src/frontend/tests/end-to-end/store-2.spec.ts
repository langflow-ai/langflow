import { expect, test } from "@playwright/test";

test("should exists Store", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").isVisible();
  await page.getByTestId("button-store").isEnabled();
});

test("should not have an API key", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(2000);

  await page.getByText("API Key Error").isVisible();
});

test("should find a searched Component on Store", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("search-store-input").fill("File Loader");
  await page.getByTestId("search-store-button").click();
  await page.getByText("File Loader").isVisible();

  await page.getByTestId("search-store-input").fill("Basic RAG");
  await page.getByTestId("search-store-button").click();
  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("search-store-input").fill("YouTube QA");
  await page.getByTestId("search-store-button").click();
  await page.getByText("YouTube QA").isVisible();
});

test("should filter by tag", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("File Loader").isVisible();
  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("tag-selector-Memory").click();
  await page.getByText("MP3 QA12").isVisible();

  await page.getByTestId("tag-selector-Chain").click();
  await page.getByText("There are no").isVisible();
  await page.getByTestId("tag-selector-Chain").click();

  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByText("MP3 QA12").isVisible();
  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByTestId("tag-selector-Memory").click();

  await page.getByText("Basic RAG").isVisible();
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
