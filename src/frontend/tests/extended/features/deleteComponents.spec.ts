import * as dotenv from "dotenv";
import path from "path";
import { test } from "../../fixtures";

test(
  "should delete a component (requires store API key)",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await page.goto("/");
    await page.waitForTimeout(1000);
    await page.getByTestId("button-store").click();
    await page.waitForTimeout(1000);
    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });
    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");
    await page.getByTestId("api-key-save-button-store").click();
    await page.waitForTimeout(1000);
    await page.getByText("Success! Your API Key has been saved.").isVisible();
    await page.waitForTimeout(1000);
    await page.getByTestId("button-store").click();

    await page.getByTestId("install-Basic RAG").click();
    await page.waitForTimeout(5000);
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();
    if (await page.getByText("Components").first().isVisible()) {
      await page.getByText("Components").first().click();
      await page.getByText("Basic RAG").first().isVisible();
      await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
        timeout: 100000,
      });
      await page.getByTestId("home-dropdown-menu").first().click();
      await page.getByTestId("icon-Trash2").click();
      await page
        .getByText("Are you sure you want to delete the selected component?")
        .isVisible();
      await page.getByText("Delete").nth(1).click();
      await page.waitForTimeout(1000);
      await page.getByText("Successfully").first().isVisible();
    }
  },
);
