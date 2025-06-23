import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// TODO: This test needs to be rebuilt/refactored
test.skip(
  "truncated values must be displayed correctly",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await page.getByTestId("input-list-plus-btn_urls-0").click();

    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://docs.langflow.org/");

    await page
      .getByTestId("inputlist_str_urls_1")
      .fill("https://www.langflow.org/");

    await page.getByTitle("fit view").click();

    await page.getByTestId("default_slider_display_value").click();
    await page.getByTestId("slider_input").fill("5");

    await page.getByTestId("button_run_url").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 3,
    });

    await page
      .getByTestId("output-inspection-extracted pages-urlcomponent")
      .click();

    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.waitForSelector("text=truncated", {
      timeout: 3000,
    });

    const trucatedWordCount = await page.getByText(`[truncated`).count();
    expect(trucatedWordCount).toBeGreaterThan(0);

    expect(page.locator("span.ag-header-cell-text").nth(1)).toHaveText("url");

    expect(page.locator("span[data-ref=lbRecordCount]").first()).toHaveText(
      "100",
    );
  },
);
