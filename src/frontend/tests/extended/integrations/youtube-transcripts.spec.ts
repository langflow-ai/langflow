import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.skip(
  "user should be able to use youtube transcripts component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("youtube");

    await page.getByTestId("youtubeYouTube Transcripts").hover();
    await page.getByTestId("add-component-button-youtube-transcripts").click();

    await page.getByTestId("fit_view").click();

    let outdatedComponents = await page.getByTestId("update-button").count();

    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    await page
      .getByTestId("textarea_str_url")
      .fill("https://www.youtube.com/watch?v=VqhCQZaH4Vs");

    await page.getByTestId("fit_view").click();

    await page.getByTestId("button_run_youtube transcripts").click();

    await page.waitForSelector("text=built successfully", { timeout: 3000 });

    await page
      .getByTestId("output-inspection-transcript-youtube-transcripts")
      .first()
      .click();
    await page.waitForSelector("text=Component Output", { timeout: 3000 });
    await page.getByRole("gridcell").first().click();
    const value = await page.getByPlaceholder("Empty").inputValue();
    expect(value.length).toBeGreaterThan(10);
  },
);
