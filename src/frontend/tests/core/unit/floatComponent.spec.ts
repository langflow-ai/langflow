import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  addParameterToNode,
  closeParametersPanel,
} from "../../utils/open-advanced-options";

test(
  "FloatComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("nvidia");

    await page.waitForSelector('[data-testid="nvidiaNVIDIA"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("nvidiaNVIDIA")
      .hover()
      .then(async () => {
        // Wait for the API request to complete after clicking the add button
        const responsePromise = page.waitForResponse(
          (response) =>
            response.url().includes("/api/v1/custom_component/update") &&
            response.status() === 200,
        );
        await page.getByTestId("add-component-button-nvidia").click();
        await responsePromise; // Wait for the request to complete
      });

    //add

    await page.getByTestId("title-NVIDIA").click();

    // LE-1810: the parameters panel adds the hidden field to the node; the
    // value is edited on the node itself.
    await addParameterToNode(page, "seed");

    await closeParametersPanel(page);

    await adjustScreenView(page);

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
  },
);
