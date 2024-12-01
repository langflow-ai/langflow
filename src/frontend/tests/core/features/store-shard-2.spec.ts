import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

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

    await page.getByTestId("api-key-button-store").click();

    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await page.waitForTimeout(1000);
    await page.getByText("Success! Your API Key has been saved.").isVisible();

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

    await page.getByText("Basic RAG").isVisible();
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

  await page.getByTestId("api-key-button-store").click();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");

  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(1000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

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
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForTimeout(1000);

  const randomName = Math.random().toString(36).substring(2);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);
  const flowName = await page.getByTestId("flow_name").innerText();
  await page.getByTestId("flow_name").click();
  await page.getByText("Flow Settings").click();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await page.getByPlaceholder("Flow name").fill(randomName);
  await page.getByText("Save").last().click();

  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 100000,
  });

  await page.getByTestId("shared-button-flow").first().click();
  await page.getByText("Name:").isVisible();
  await page.getByText("Description:").isVisible();
  await page.getByText("Set workflow status to public").isVisible();
  await page
    .getByText(
      "Attention: API keys in specified fields are automatically removed upon sharing.",
    )
    .isVisible();
  await page.getByText("Export").first().isVisible();
  await page.getByText("Share Flow").first().isVisible();

  await page.waitForTimeout(3000);

  await page.getByText("Agent").first().isVisible();
  await page.getByText("Memory").first().isVisible();
  await page.getByText("Chain").first().isVisible();
  await page.getByText("Vector Store").first().isVisible();
  await page.getByText("Prompt").last().isVisible();
  await page.getByTestId("public-checkbox").isChecked();
  await page.getByText(flowName).last().isVisible();
  await page.getByText(flowDescription).last().isVisible();
  await page.waitForTimeout(1000);
  await page.getByText("Flow shared successfully").last().isVisible();
});
