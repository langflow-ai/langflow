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

    await page.waitForTimeout(2000);

    await page.getByTestId("youtubeYouTube Transcripts").hover();
    await page.getByTestId("add-component-button-youtube-transcripts").click();

    await page.getByTestId("fit_view").click();
    await handleOutdatedComponents(page);

    await page
      .getByTestId("textarea_str_url")
      .fill("https://www.youtube.com/watch?v=VqhCQZaH4Vs");

    await page.getByTestId("fit_view").click();

    await page.getByTestId("button_run_youtube transcripts").click();

    try {
      await Promise.race([
        page.waitForSelector("text=built successfully", { timeout: 60000 }),
        page.waitForSelector("text=Failed to get YouTube transcripts", {
          timeout: 60000,
        }),
      ]);

      await page
        .getByTestId("output-inspection-transcript-youtube-transcripts")
        .first()
        .click();

      await page.waitForSelector("text=Component Output", { timeout: 30000 });

      const cell = await page.getByRole("gridcell").first();
      await cell.click();

      const value = await page.getByPlaceholder("Empty").inputValue();
      expect(value.length).toBeGreaterThan(10);
      expect(value).toContain(" ");
      expect(value.split(" ").length).toBeGreaterThan(5);
    } catch (error) {
      throw error;
    }
  },
);

async function handleOutdatedComponents(page) {
  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }
}
