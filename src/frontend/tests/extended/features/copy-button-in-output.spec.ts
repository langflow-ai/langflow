import { expect, test } from "../../fixtures";
import { addCustomComponent } from "../../utils/add-custom-component";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to copy JSON from output",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="disclosure-data"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data").click();

    await page
      .getByTestId("dataAPI Request")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-api-request").click();

        await page.waitForTimeout(500);

        await page
          .getByTestId("popover-anchor-input-url_input")
          .first()
          .fill("https://www.google.com");
      });

    await page.getByTestId("button_run_api request").click();

    await page.waitForSelector("text=Running", {
      timeout: 30000,
      state: "visible",
    });

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("output-inspection-api response-apirequest").click();

    await page.waitForSelector("text=Component Output", { timeout: 30000 });

    await page.getByTitle("Copy JSON to clipboard").click();

    await page.waitForSelector("text=JSON copied to clipboard", {
      timeout: 30000,
    });

    await page.getByText("tree").last().click();

    await page.waitForTimeout(1000);

    await page.locator(".jse-key").first().click();

    await page.waitForTimeout(500);

    await page.getByTitle("Copy (Ctrl+C)").click();

    await page.waitForSelector("text=Copied to clipboard", { timeout: 30000 });
  },
);
