import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";

test(
  "should filter by tag",
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
      .getByPlaceholder(TEXTS.placeholderApiKey)
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await page.waitForTimeout(1000);
    await expect(page.getByText(TEXTS.toastApiKeySaved)).toBeVisible();
    await page.getByTestId("button-store").click();
    await page.waitForTimeout(1000);

    async function safeClick(selector: string) {
      await page.getByTestId(selector).waitFor({ state: "visible" });
      await page.getByTestId(selector).click();
      await page.waitForTimeout(500); // Wait for UI updates
    }

    // Agent section
    await safeClick("tag-selector-Agent");
    await page.getByText("File Loader").waitFor({ state: "visible" });
    await safeClick("tag-selector-Agent");
    await page.getByText("Website Content").waitFor({ state: "visible" });

    // Memory section
    await safeClick("tag-selector-Memory");
    await page.getByText("MP3 QA12").waitFor({ state: "visible" });

    // Chain section
    await safeClick("tag-selector-Chain");
    await page.getByText("ChatOllama").waitFor({ state: "visible" });
    await safeClick("tag-selector-Chain");

    // Vector Store section
    await safeClick("tag-selector-Vector Store");
    await page.getByText("MP3 QA12").waitFor({ state: "visible" });
    await safeClick("tag-selector-Vector Store");
    await safeClick("tag-selector-Memory");

    await expect(page.getByText(TEXTS.templateBasicRag)).toBeVisible();
  },
);
