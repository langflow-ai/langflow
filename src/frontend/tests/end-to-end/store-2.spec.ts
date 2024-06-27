import { expect, test } from "@playwright/test";

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
