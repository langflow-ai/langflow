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

test("should like and add components and flows", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();

  await page.waitForTimeout(2000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(5000);

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

  await page.getByText("Components").first().click();
  await page.getByText("Basic RAG").first().isVisible();
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
