import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "Invoice Summarizer",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY || !process?.env?.NEEDLE_API_KEY,
      "OPENAI_API_KEY and NEEDLE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Invoice Summarizer" }).click();

    await initialGPTsetup(page);

    // Configure Needle Search Knowledge Base
    await page
      .getByTestId("input_str_needle_api_key")
      .fill(process.env.NEEDLE_API_KEY || "");
    await page
      .getByTestId("input_str_collection_id")
      .fill(process.env.NEEDLE_COLLECTION_ID || "");

    // Run the flow
    await page.getByTestId("button_run_chat output").click();

    // Wait for the flow to build successfully
    await page.waitForSelector("text=built successfully", { timeout: 30000 });
    await page.getByText("built successfully").last().click({
      timeout: 30000,
    });

    // Switch to Playground
    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByPlaceholder(
        "No chat input variables found. Click to run your flow.",
        { exact: true },
      )
      .last()
      .isVisible();

    // Verify key elements of the expense analysis are visible
    await page.getByText("Search Results Summary").last().isVisible();
    await page.getByText("expenses").last().isVisible();
    await page.getByText("invoice").last().isVisible();
    await page.getByText("vendor").last().isVisible();
  },
);
