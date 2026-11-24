import { test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "refresh dropdown list",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Portfolio Website Code Generator" })
      .click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await page.waitForTimeout(3000);

    await page.getByText("Loading Options").isVisible({ timeout: 5000 });
  },
);
