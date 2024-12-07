import { expect, test } from "@playwright/test";

test(
  "user should be able to use youtube transcripts component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

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

    await page.getByTestId("output-inspection-data").first().click();

    await page.waitForSelector("text=Component Output", { timeout: 30000 });

    await page.getByRole("gridcell").first().click();

    const value = await page.getByPlaceholder("Empty").inputValue();
    expect(value.length).toBeGreaterThan(10);
  },
);
