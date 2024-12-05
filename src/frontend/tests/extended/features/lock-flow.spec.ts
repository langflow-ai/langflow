import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

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

    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("lock_unlock").click();
    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });
    expect(page.getByTestId("icon-Lock")).toBeVisible();

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });
    expect(page.getByTestId("icon-Lock")).toBeVisible();

    await page.getByTestId("lock_unlock").click();
    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
    });
    expect(page.getByTestId("icon-LockOpen")).toBeVisible();

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
    });
    expect(page.getByTestId("icon-LockOpen")).toBeVisible();
  },
);
