import { test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
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

    await adjustScreenView(page, { numberOfZoomOut: 3 });
  });
});
