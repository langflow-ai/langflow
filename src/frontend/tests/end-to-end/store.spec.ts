import { expect, test } from "@playwright/test";

test("should exists Store", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").isVisible();
  await page.getByTestId("button-store").isEnabled();
});

test("should not have an API key", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(2000);

  await page.getByText("API Key Error").isVisible();
});

test("should find a searched Component on Store", async ({ page }) => {
  await page.goto("http://localhost:3000/");
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
  await page.goto("http://localhost:3000/");
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
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.getByText("Alphabetical").click();

  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.getByText("Popular").click();

  await page.getByText("Basic RAG").isVisible();
});

test("should filter by type", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Website Content QA").isVisible();

  await page.getByTestId("flows-button-store").click();
  await page.waitForTimeout(3000);

  let iconGroup = await page.getByTestId("icon-Group").count();
  expect(iconGroup).not.toBe(0);

  await page.getByText("icon-ToyBrick").isHidden();

  await page.getByTestId("components-button-store").click();
  await page.waitForTimeout(3000);

  await page.getByTestId("icon-Group").isHidden();
  let toyBrick = await page.getByTestId("icon-ToyBrick").count();
  expect(toyBrick).not.toBe(0);

  await page.getByTestId("all-button-store").click();
  await page.waitForTimeout(3000);

  iconGroup = await page.getByTestId("icon-Group").count();
  toyBrick = await page.getByTestId("icon-ToyBrick").count();

  if (iconGroup === 0 || toyBrick === 0) {
    expect(false).toBe(true);
  }
});

test("should add API-KEY", async ({ page }) => {
  await page.goto("http://localhost:3000/");
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

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isVisible();

  await page.getByTestId("api-key-button-store").click();
  await page
    .getByPlaceholder("Insert your API Key")
    .fill("x1fOKU0v2e5zL5d-BZW6CxZBZvoyuFgF");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();
});

test("should like and add components and flows", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill("x1fOKU0v2e5zL5d-BZW6CxZBZvoyuFgF");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();

  const likedValue = await page
    .getByTestId("likes-Website Content QA")
    .innerText();

  await page.getByTestId("like-Website Content QA").click();

  await page.waitForTimeout(5000);
  const likedValueAfter = await page
    .getByTestId("likes-Website Content QA")
    .innerText();

  if (Number(likedValue) === Number(likedValueAfter)) {
    expect(false).toBe(true);
  }

  const downloadValue = await page
    .getByTestId("downloads-Website Content QA")
    .innerText();

  await page.getByTestId("install-Website Content QA").click();
  await page.waitForTimeout(2000);
  await page.getByText("Flow Installed Successfully").isVisible();
  await page.waitForTimeout(5000);

  const downloadValueAfter = await page
    .getByTestId("downloads-Website Content QA")
    .innerText();

  if (Number(downloadValue) === Number(downloadValueAfter)) {
    expect(false).toBe(true);
  }

  await page.getByTestId("install-Basic RAG").click();
  await page.waitForTimeout(2000);
  await page.getByText("Component Installed Successfully").isVisible();
  await page.waitForTimeout(5000);

  await page.getByText("My Collection").click();
  await page.getByText("Website Content QA").first().isVisible();

  await page.getByTestId("sidebar-nav-Components").click();
  await page.getByText("Basic RAG").first().isVisible();
});
