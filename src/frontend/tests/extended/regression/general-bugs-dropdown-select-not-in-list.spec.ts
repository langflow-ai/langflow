import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to select a value from dropdown that is not in the list",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");

    await page.waitForSelector('[data-testid="modelsOpenAI"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("modelsOpenAI")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-openai").last().click();
      });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("dropdown_search_input").click();
    await page
      .getByTestId("dropdown_search_input")
      .fill("this is a test langflow");
    await page.keyboard.press("Enter");

    await page.waitForTimeout(500);

    const value = await page
      .getByTestId("value-dropdown-dropdown_str_model_name")
      .textContent();
    expect(value?.trim()).toBe("this is a test langflow");
  },
);
