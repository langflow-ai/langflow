import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use youtube transcripts component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("youtube");

    await page.waitForSelector('[id="toolsYouTube Transcripts"]', {
      timeout: 3000,
    });

    await page
      .locator('//*[@id="toolsYouTube Transcripts"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("fit_view").click();

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    await page
      .getByTestId("textarea_str_url")
      .fill("https://www.youtube.com/watch?v=VqhCQZaH4Vs");

    await page.getByTestId("button_run_youtube transcripts").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("output-inspection-transcription").first().click();

    await page.waitForSelector("text=Component Output", { timeout: 30000 });

    await page.getByRole("gridcell").first().click();

    const value = await page.getByPlaceholder("Empty").inputValue();
    expect(value.length).toBeGreaterThan(10);
  },
);
