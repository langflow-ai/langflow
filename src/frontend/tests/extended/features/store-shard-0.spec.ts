import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.skip("should exists Store", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page, { skipModal: true });

  await expect(page.getByTestId("button-store")).toBeVisible();
  await page.getByTestId("button-store").isEnabled();
});

test.skip(
  "should not have an API key",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    await page.getByTestId("button-store").click();

    await expect(page.getByText("API Key Error")).toBeVisible();
  },
);
