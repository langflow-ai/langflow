import { test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Flow Page tests", () => {
  test("save", { tag: ["@release"] }, async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 3000,
      },
    );

    await page.getByTestId("sidebar-custom-component-button").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTitle("fit view").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    await page.getByTestId("canvas_controls_dropdown").click();
  });
});
