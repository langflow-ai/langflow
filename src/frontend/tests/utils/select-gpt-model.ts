import type { Page } from "@playwright/test";

export const selectGptModel = async (page: Page) => {
  const gptModelDropdownCount = await page.getByTestId("model_model").count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    await page.getByTestId("model_model").nth(i).click();
    await page.waitForSelector('[role="listbox"]', { timeout: 10000 });
    await page.getByTestId("gpt-4o-mini-option").click();
  }
};
