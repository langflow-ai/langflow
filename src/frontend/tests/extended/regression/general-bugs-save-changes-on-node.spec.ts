import { expect, Page, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

async function verifyTextareaValue(page: Page, value: string) {
  await page.getByTestId("textarea_str_input_value").fill(value);
  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[data-testid="list-card"]', {
    timeout: 3000,
  });

  await page.getByTestId("list-card").first().click();

  await page.waitForSelector('[data-testid="textarea_str_input_value"]', {
    timeout: 3000,
  });

  const inputValue = await page
    .getByTestId("textarea_str_input_value")
    .inputValue();
  expect(inputValue).toBe(value);
}

test(
  "any changes on the node must be saved on user interaction",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const randomValues = Array.from({ length: 4 }, () =>
      Math.random().toString(36).substring(2, 15),
    );

    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");

    await page
      .getByTestId("outputsText Output")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-output").click();
      });

    await page.waitForSelector('[data-testid="title-Text Output"]', {
      timeout: 3000,
    });

    // Verify each random value
    for (const value of randomValues) {
      await verifyTextareaValue(page, value);
    }
  },
);
