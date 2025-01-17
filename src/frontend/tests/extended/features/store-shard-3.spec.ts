import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "should order the visualization (requires store API key)",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");

    await page.getByTestId("button-store").click();

    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await expect(page.getByText("API key saved successfully")).toBeVisible({
      timeout: 5000,
    });

    await page.getByTestId("button-store").click();

    await expect(page.getByText("Basic RAG")).toBeVisible({ timeout: 30000 });

    await page.getByTestId("select-order-store").click();

    await page.getByText("Alphabetical").click();

    await page.getByText("Album Cover Builder").isVisible();

    await page.getByTestId("select-order-store").click();
    await page.getByText("Popular").click();

    await page.getByText("Basic RAG").isVisible();
  },
);

test(
  "should filter by type (requires store API key)",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await page.goto("/");
    await page.getByTestId("button-store").click();
    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");
    await page.getByTestId("api-key-save-button-store").click();
    await expect(page.getByText("API key saved successfully")).toBeVisible({
      timeout: 5000,
    });
    await page.getByTestId("button-store").click();
    await page.waitForSelector('[data-testid="likes-Website Content QA"]', {
      timeout: 100000,
    });
    await page.getByText("Website Content QA").isVisible();
    await page.waitForSelector('[data-testid="flows-button-store"]', {
      timeout: 100000,
    });
    await page.getByTestId("flows-button-store").click();
    await page.waitForSelector('[data-testid="icon-Group"]', {
      timeout: 100000,
    });
    let iconGroup = await page.getByTestId("icon-Group")?.count();
    expect(iconGroup).not.toBe(0);
    await page.getByText("icon-ToyBrick").last().isHidden();
    await page.waitForSelector('[data-testid="components-button-store"]', {
      timeout: 100000,
    });
    await page.getByTestId("components-button-store").click();
    await expect(page.getByTestId("icon-Group").last()).toBeHidden({
      timeout: 30000,
    });
    await page.waitForSelector('[data-testid="icon-ToyBrick"]', {
      timeout: 100000,
    });
    let toyBrick = await page.getByTestId("icon-ToyBrick")?.count();
    expect(toyBrick).not.toBe(0);
    await page.waitForSelector('[data-testid="all-button-store"]', {
      timeout: 100000,
    });
    await page.getByTestId("all-button-store").click();
    await page.waitForSelector('[data-testid="icon-Group"]', {
      timeout: 100000,
    });
    await page.waitForSelector('[data-testid="icon-ToyBrick"]', {
      timeout: 100000,
    });
    let iconGroupAllCount = await page.getByTestId("icon-Group")?.count();
    await page.waitForTimeout(500);
    let toyBrickAllCount = await page.getByTestId("icon-ToyBrick")?.count();
    await page.waitForTimeout(500);
    if (iconGroupAllCount === 0 || toyBrickAllCount === 0) {
      expect(false).toBe(true);
    }
  },
);
