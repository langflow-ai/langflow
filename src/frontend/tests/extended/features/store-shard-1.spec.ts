import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";

test.skip(
  "should like and add components and flows (requires store API key)",
  { tag: ["@release"] },
  async ({ page }) => {
    skipIfMissing.storeApiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page, { skipModal: true });

    await page.getByText(TEXTS.close, { exact: true }).click();
    await page.waitForTimeout(1000);
    await page.getByTestId("button-store").click();
    await page.waitForTimeout(1000);
    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });
    await page
      .getByPlaceholder(TEXTS.placeholderApiKey)
      .fill(process.env.STORE_API_KEY ?? "");
    await page.getByTestId("api-key-save-button-store").click();
    await page.waitForTimeout(1000);
    await expect(page.getByText(TEXTS.toastApiKeySaved)).toBeVisible();
    await page.waitForTimeout(1000);
    await page.getByTestId("button-store").click();
    await page.waitForSelector('[data-testid="likes-Website Content QA"]', {
      timeout: 100000,
    });
    await expect(page.getByTestId("likes-Website Content QA")).toBeVisible();
    await page.waitForTimeout(1000);
    const likedValue = await page
      .getByTestId("likes-Website Content QA")
      .innerText();
    await page.getByTestId("like-Website Content QA").click();
    await page.waitForSelector('[data-testid="likes-Website Content QA"]', {
      timeout: 100000,
    });
    await page.waitForTimeout(1000);
    const likedValueAfter = await page
      .getByTestId("likes-Website Content QA")
      .innerText();
    expect(Number(likedValueAfter)).not.toBe(Number(likedValue));
    await page.waitForSelector('[data-testid="downloads-Website Content QA"]', {
      timeout: 100000,
    });
    const downloadValue = await page
      .getByTestId("downloads-Website Content QA")
      .innerText();
    await page.waitForTimeout(1000);
    await page.getByTestId("install-Website Content QA").click();
    await page.waitForTimeout(1000);
    await expect(page.getByText("Flow Installed Successfully")).toBeVisible();
    await page.waitForTimeout(1000);
    const downloadValueAfter = await page
      .getByTestId("downloads-Website Content QA")
      .innerText();
    expect(Number(downloadValueAfter)).not.toBe(Number(downloadValue));
    await page.getByTestId("install-Basic RAG").click();
    await page.waitForTimeout(1000);
    await expect(
      page.getByText("Component Installed Successfully"),
    ).toBeVisible();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();
    await page.waitForSelector("text=Website Content QA", { timeout: 30000 });
    await expect(page.getByText("Website Content QA").first()).toBeVisible();
    await page.getByText(TEXTS.labelComponents).first().click();
    await page.waitForTimeout(1000);
    await page.waitForSelector("text=Basic RAG", { timeout: 30000 });
    await expect(page.getByText(TEXTS.templateBasicRag).first()).toBeVisible();
  },
);

test.skip(
  "should find a searched Component on Store (requires store API key)",
  { tag: ["@release"] },
  async ({ page }) => {
    skipIfMissing.storeApiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page, { skipModal: true });

    await page.waitForTimeout(1000);

    await page.getByTestId("button-store").click();
    await page.waitForTimeout(1000);

    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderApiKey)
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await page.waitForTimeout(1000);
    await expect(page.getByText(TEXTS.toastApiKeySaved)).toBeVisible();
    await page.waitForTimeout(1000);

    await page.getByTestId("button-store").click();

    await page.waitForSelector('[data-testid="search-store-input"]', {
      timeout: 100000,
    });

    await page.getByTestId("search-store-input").fill("File Loader");
    await page.getByTestId("search-store-button").click();
    await expect(page.getByText("File Loader")).toBeVisible();
    await page.getByTestId("search-store-input").fill("Basic RAG");
    await page.getByTestId("search-store-button").click();
    await expect(page.getByText(TEXTS.templateBasicRag)).toBeVisible();
    await page.getByTestId("search-store-input").fill("YouTube QA");
    await page.getByTestId("search-store-button").click();
    await expect(page.getByText("YouTube QA")).toBeVisible();
  },
);
