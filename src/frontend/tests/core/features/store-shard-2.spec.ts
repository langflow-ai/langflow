import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { renameFlow } from "../../utils/rename-flow";

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

test("should share component with share button", async ({ page }) => {
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
  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await awaitBootstrapTest(page, {
    skipGoto: true,
  });

  await page.waitForTimeout(1000);

  const randomName = Math.random().toString(36).substring(2);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await renameFlow(page, { flowName: randomName });

  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 100000,
  });

  await page.getByTestId("shared-button-flow").first().click();
  await expect(page.getByText("Name:")).toBeVisible();
  await expect(page.getByText("Description:")).toBeVisible();
  await expect(page.getByText("Set workflow status to public")).toBeVisible();
  await page
    .getByText(
      "Attention: API keys in specified fields are automatically removed upon sharing.",
    )
    .isVisible();
  await expect(page.getByText("Export").first()).toBeVisible();
  await expect(page.getByText("Share Flow").first()).toBeVisible();
  await page.waitForTimeout(3000);

  await expect(page.getByText("Agent").first()).toBeVisible();
  await expect(page.getByText("Memory").first()).toBeVisible();
  await expect(page.getByText("Chain").first()).toBeVisible();
  await expect(page.getByText("Vector Store").first()).toBeVisible();
  await expect(page.getByText("Prompt").last()).toBeVisible();
  await page.getByTestId("public-checkbox").isChecked();

  const flowName = await page.getByTestId("input-flow-name").inputValue();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await expect(page.getByText(flowName).last()).toBeVisible();
  await expect(page.getByText(flowDescription).last()).toBeVisible();
  await page.waitForTimeout(1000);

  await expect(page.getByText("Flow shared successfully").last()).toBeVisible();
});
