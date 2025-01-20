import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use youtube transcripts component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Add component
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("youtube");

    // Wait for search results to stabilize
    await page.waitForTimeout(2000);

    // Add the component
    await page.getByTestId("youtubeYouTube Transcripts").hover();
    await page.getByTestId("add-component-button-youtube-transcripts").click();

    // Fit view and handle any outdated components
    await page.getByTestId("fit_view").click();
    await handleOutdatedComponents(page);

    // Fill in the YouTube URL
    await page
      .getByTestId("textarea_str_url")
      .fill("https://www.youtube.com/watch?v=VqhCQZaH4Vs");

    await page.getByTestId("fit_view").click();

    // Click run and wait for processing
    await page.getByTestId("button_run_youtube transcripts").click();

    // Add more specific success criteria
    try {
      // Wait for either success or error indicators
      await Promise.race([
        page.waitForSelector("text=built successfully", { timeout: 60000 }),
        page.waitForSelector("text=Failed to get YouTube transcripts", {
          timeout: 60000,
        }),
      ]);

      // Check output
      await page.getByTestId("output-inspection-transcript").first().click();
      await page.waitForSelector("text=Component Output", { timeout: 30000 });

      const cell = await page.getByRole("gridcell").first();
      await cell.click();

      const value = await page.getByPlaceholder("Empty").inputValue();

      // Verify output content
      expect(value.length).toBeGreaterThan(10);

      // Additional validation that output is actually transcript content
      expect(value).toContain(" "); // Should contain spaces between words
      expect(value.split(" ").length).toBeGreaterThan(5); // Should have multiple words
    } catch (error) {
      // Take screenshot on failure for debugging
      throw error;
    }
  },
);

// Helper function to handle outdated components
async function handleOutdatedComponents(page) {
  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000); // Give time for UI to update
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }
}
