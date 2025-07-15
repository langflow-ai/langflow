import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should order the visualization (requires store API key)",
  { tag: ["@release"] },
  async ({ page, context }) => {
    test.skip();

    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page, { skipModal: true });

    await page.waitForTimeout(1000);
    await page.waitForSelector('[data-testid="button-store"]', {
      state: "visible",
      timeout: 10000,
    });

    const [newPageStore] = await Promise.all([
      context.waitForEvent("page"),
      page.getByTestId("button-store").click(),
    ]);

    await newPageStore.waitForTimeout(1000);

    await newPageStore.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await newPageStore.getByTestId("sidebar-nav-Langflow Store").click();

    await newPageStore
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");

    await newPageStore.getByTestId("api-key-save-button-store").click();

    await expect(
      newPageStore.getByText("API key saved successfully"),
    ).toBeVisible({
      timeout: 5000,
    });

    await newPageStore.getByTestId("back_page_button").click();

    await newPageStore.waitForTimeout(1000);

    const newPageStore2 = await context.newPage();

    await newPageStore2.goto("/store");

    await newPageStore2.waitForTimeout(1000);

    await expect(newPageStore2.getByText("Basic RAG")).toBeVisible({
      timeout: 30000,
    });

    await newPageStore2.getByTestId("select-order-store").click();

    await newPageStore2.getByText("Alphabetical").click();

    await newPageStore2.getByText("Album Cover Builder").isVisible();

    await newPageStore2.getByTestId("select-order-store").click();
    await newPageStore2.getByText("Popular").click();

    await newPageStore2.getByText("Basic RAG").isVisible();
  },
);

test(
  "should filter by type (requires store API key)",
  { tag: ["@release"] },
  async ({ page, context }) => {
    test.skip();
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page, { skipModal: true });

    await page.waitForSelector('[data-testid="button-store"]', {
      state: "visible",
      timeout: 10000,
    });

    await page.getByTestId("button-store").click();

    const newPageStore = await context.waitForEvent("page", { timeout: 30000 });

    await newPageStore.waitForTimeout(1000);

    await newPageStore.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await newPageStore.getByTestId("sidebar-nav-Langflow Store").click();

    await newPageStore
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");
    await newPageStore.getByTestId("api-key-save-button-store").click();
    await expect(
      newPageStore.getByText("API key saved successfully"),
    ).toBeVisible({
      timeout: 5000,
    });

    await newPageStore.getByTestId("back_page_button").click();

    await newPageStore.waitForTimeout(1000);

    const newPageStore2 = await context.newPage();

    await newPageStore2.goto("/store");

    await newPageStore2.waitForTimeout(1000);

    await newPageStore2.waitForSelector(
      '[data-testid="likes-Website Content QA"]',
      {
        timeout: 100000,
      },
    );
    await newPageStore2.getByText("Website Content QA").isVisible();
    await newPageStore2.waitForSelector('[data-testid="flows-button-store"]', {
      timeout: 100000,
    });
    await newPageStore2.getByTestId("flows-button-store").click();
    await newPageStore2.waitForSelector('[data-testid="icon-Group"]', {
      timeout: 100000,
    });
    const iconGroup = await newPageStore2.getByTestId("icon-Group")?.count();
    expect(iconGroup).not.toBe(0);
    await newPageStore2.getByText("icon-ToyBrick").last().isHidden();
    await newPageStore2.waitForSelector(
      '[data-testid="components-button-store"]',
      {
        timeout: 100000,
      },
    );
    await newPageStore2.getByTestId("components-button-store").click();
    await expect(newPageStore2.getByTestId("icon-Group").last()).toBeHidden({
      timeout: 30000,
    });
    await newPageStore2.waitForSelector('[data-testid="icon-ToyBrick"]', {
      timeout: 100000,
    });
    const toyBrick = await newPageStore2.getByTestId("icon-ToyBrick")?.count();
    expect(toyBrick).not.toBe(0);
    await newPageStore2.waitForSelector('[data-testid="all-button-store"]', {
      timeout: 100000,
    });
    await newPageStore2.getByTestId("all-button-store").click();
    await newPageStore2.waitForSelector('[data-testid="icon-Group"]', {
      timeout: 100000,
    });
    await newPageStore2.waitForSelector('[data-testid="icon-ToyBrick"]', {
      timeout: 100000,
    });
    const iconGroupAllCount = await newPageStore2
      .getByTestId("icon-Group")
      ?.count();
    await newPageStore2.waitForTimeout(500);
    const toyBrickAllCount = await newPageStore2
      .getByTestId("icon-ToyBrick")
      ?.count();
    await newPageStore2.waitForTimeout(500);
    if (iconGroupAllCount === 0 || toyBrickAllCount === 0) {
      expect(false).toBe(true);
    }
  },
);
