import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "Invoice Summarizer",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY ||
        !process?.env?.NEEDLE_API_KEY ||
        !process?.env?.NEEDLE_COLLECTION_ID,
      "OPENAI_API_KEY, NEEDLE_API_KEY, and NEEDLE_COLLECTION_ID required to run this test",
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

    // Switch to Playground
    await page.getByRole("button", { name: "Playground", exact: true }).click();

    // Wait for the playground to be ready
    const inputPlaceholder = page
      .getByPlaceholder(
        "No chat input variables found. Click to run your flow.",
        { exact: true },
      )
      .last();

    await expect(inputPlaceholder).toBeVisible({ timeout: 10000 });

    // Verify initial response is displayed
    await expect(page.getByText("Search Results Summary")).toBeVisible({
      timeout: 15000,
    });

    // Verify that specific invoice-related data appears in the results
    const keyTerms = ["expenses", "invoice", "vendor"];
    for (const term of keyTerms) {
      await expect(page.getByText(term, { exact: false })).toBeVisible({
        timeout: 5000,
      });
    }

    // Test interaction with the flow by adding a specific query
    // Click the input field and type a query
    await inputPlaceholder.click();
    await page.keyboard.type("Summarize the total expenses from last month");
    await page.keyboard.press("Enter");

    // Wait for response to the specific query
    await expect(page.getByText("Search Results Summary")).toBeVisible({
      timeout: 20000,
    });

    // Verify that expense summary information appears in the response
    await expect(page.getByText("expenses", { exact: false })).toBeVisible({
      timeout: 10000,
    });

    // Test error handling - invalid query
    await page.keyboard.type("xyz123$%^NonSensicalQuery");
    await page.keyboard.press("Enter");

    // Wait for the response, which should still show search results or appropriate message
    await expect(
      page
        .getByText("Search Results", { exact: false })
        .or(page.getByText("no relevant", { exact: false })),
    ).toBeVisible({ timeout: 20000 });

    // Cleanup - Reset the session
    await page.getByTestId("side_nav_options_all-templates").click();
  },
);
