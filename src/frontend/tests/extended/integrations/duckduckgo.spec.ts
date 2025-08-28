import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use duckduckgo search component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("duck");

    await page.waitForSelector(
      '[data-testid="disclosure-bundles-duckduckgo"]',
      {
        timeout: 3000,
      },
    );

    await page
      .getByTestId("duckduckgoDuckDuckGo Search")
      .hover()
      .then(async () => {
        await page
          .getByTestId("add-component-button-duckduckgo-search")
          .click();
      });
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill("what is langflow?");

    await page.getByTestId("button_run_duckduckgo search").click();

    const result = await Promise.race([
      page.waitForSelector("text=built successfully", { timeout: 30000 }),
      page.waitForSelector("text=ratelimit", { timeout: 30000 }),
    ]);

    if (result) {
      const isBuiltSuccessfully =
        (await page.evaluate((el) => el.textContent, result))?.includes(
          "built successfully",
        ) ?? false;

      await page
        .getByTestId("output-inspection-dataframe-duckduckgosearchcomponent")
        .first()
        .click();

      if (isBuiltSuccessfully) {
        await page.getByRole("gridcell").first().click();
        const searchResults = await page.getByPlaceholder("Empty").inputValue();
        expect(searchResults.length).toBeGreaterThan(10);
        expect(searchResults.toLowerCase()).toContain("langflow");
      } else {
        const value = await page.getByPlaceholder("Empty").inputValue();
        expect(value.length).toBeGreaterThan(10);
        expect(value.toLowerCase()).toContain("ratelimit");
      }
    }
  },
);
