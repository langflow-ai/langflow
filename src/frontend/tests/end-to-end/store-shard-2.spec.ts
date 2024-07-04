import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should filter by tag", async ({ page }) => {
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

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("File Loader").isVisible();
  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("tag-selector-Memory").click();
  await page.getByText("MP3 QA12").isVisible();

  await page.getByTestId("tag-selector-Chain").click();
  await page.getByText("There are no").isVisible();
  await page.getByTestId("tag-selector-Chain").click();

  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByText("MP3 QA12").isVisible();
  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByTestId("tag-selector-Memory").click();

  await page.getByText("Basic RAG").isVisible();
});

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

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.getByText("My Collection").click();
  await page.waitForTimeout(2000);

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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForTimeout(1000);

  const randomName = Math.random().toString(36).substring(2);

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);
  const flowName = await page.getByTestId("flow_name").innerText();
  await page.getByTestId("flow_name").click();
  await page.getByText("Settings").click();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await page.getByPlaceholder("Flow name").fill(randomName);
  await page.getByText("Save").last().click();
  await page.getByText("Close").last().click();

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

  await page.waitForTimeout(5000);

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
