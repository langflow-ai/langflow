import { expect, Page, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

async function verifyTextareaValue(page: Page, value: string) {
  await page
    .getByTestId("textarea_str_input_value")
    .waitFor({ state: "visible" });
  await page.getByTestId("textarea_str_input_value").fill(value);

  await expect(page.getByTestId("textarea_str_input_value")).toHaveValue(value);

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[data-testid="list-card"]', {
    timeout: 5000,
    state: "visible",
  });

  await page.getByTestId("list-card").first().click();

  await page.waitForSelector('[data-testid="textarea_str_input_value"]', {
    timeout: 5000,
    state: "visible",
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
      Math.random().toString(36).substring(2, 8),
    );

    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 10000,
      state: "visible",
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");

    await page.getByTestId("outputsText Output").waitFor({ state: "visible" });
    await page.getByTestId("add-component-button-text-output").click();

    await page.waitForSelector('[data-testid="title-Text Output"]', {
      timeout: 5000,
      state: "visible",
    });

    for (const value of randomValues) {
      try {
        await verifyTextareaValue(page, value);
      } catch (error) {
        console.error(`Failed to verify value: ${value}`, error);
        throw error;
      }
    }
  },
);
