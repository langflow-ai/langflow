import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";

test(
  "should delete a component (requires store API key)",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    skipIfMissing.storeApiKey();
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
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

    await page.getByTestId("install-Basic RAG").click();
    await page.waitForTimeout(5000);
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();
    if (await page.getByText(TEXTS.labelComponents).first().isVisible()) {
      await page.getByText(TEXTS.labelComponents).first().click();
      await expect(
        page.getByText(TEXTS.templateBasicRag).first(),
      ).toBeVisible();
      await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
        timeout: 100000,
      });
      await page.getByTestId("home-dropdown-menu").first().click();
      await page.getByTestId("icon-Trash2").click();
      await page
        .getByText("Are you sure you want to delete the selected component?")
        .isVisible();
      await page.getByText(TEXTS.delete).nth(1).click();
      await page.waitForTimeout(1000);
      await expect(page.getByText("Successfully").first()).toBeVisible();
    }
  },
);
