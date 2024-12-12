import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to lock a flow and it must be saved",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.getByTestId("lock_unlock").click();

    //ensure the UI is updated
    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
      state: "visible",
    });

    //ensure the UI is updated
    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });

    await page.getByTestId("lock_unlock").click();
    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
    });

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
      state: "visible",
    });
  },
);
