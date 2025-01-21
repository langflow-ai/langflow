import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "FloatComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("nvidia");

    await page.waitForSelector('[data-testid="modelsNVIDIA"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("modelsNVIDIA")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-nvidia").click();
      });

    await page.getByTestId("title-NVIDIA").click();

    await page.getByTestId("edit-button-modal").click();

    await page.getByTestId("showseed").click();

    await page.getByText("Close").last().click();

    await page.locator('//*[@id="int_int_seed"]').click();
    await page.locator('//*[@id="int_int_seed"]').fill("");
    await page.locator('//*[@id="int_int_seed"]').fill("3");

    let value = await page.locator('//*[@id="int_int_seed"]').inputValue();

    expect(value).toBe("3");

    await page.locator('//*[@id="int_int_seed"]').click();
    await page.locator('//*[@id="int_int_seed"]').fill("");
    await page.locator('//*[@id="int_int_seed"]').fill("-3");

    value = await page.locator('//*[@id="int_int_seed"]').inputValue();

    expect(value).toBe("-3");

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.getByText("Close").last().click();

    const plusButtonLocator = page.locator('//*[@id="int_int_edit_seed"]');
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("more-options-modal").click();
      await page.getByTestId("advanced-button-modal").click();

      await page.getByText("Close").last().click();
      await page.locator('//*[@id="int_int_seed"]').click();
      await page.getByTestId("int_int_seed").fill("");

      await page.locator('//*[@id="int_int_seed"]').fill("3");

      let value = await page.locator('//*[@id="int_int_seed"]').inputValue();

      expect(value).toBe("3");

      await page.locator('//*[@id="int_int_seed"]').click();
      await page.getByTestId("int_int_seed").fill("");

      await page.locator('//*[@id="int_int_seed"]').fill("-3");

      value = await page.locator('//*[@id="int_int_seed"]').inputValue();

      expect(value).toBe("-3");
    }
  },
);
