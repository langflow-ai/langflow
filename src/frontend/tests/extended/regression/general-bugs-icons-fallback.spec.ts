import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";

test(
  "user must be able to see icons fallback if the icon is not found",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("disclosure-data").click();
    await page.waitForTimeout(500);
    await page.getByTestId("disclosure-processing").click();
    await page.waitForTimeout(500);
    const loadingIcons = await page.getByTestId("loading-icon").count();
    expect(loadingIcons).toBe(0);
  },
);
