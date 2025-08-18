import type { Page } from "playwright/test";

export const selectGptModel = async (page: Page) => {
  const gptModelDropdownCount = await page
    .getByTestId("dropdown_str_model_name")
    .count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    await page.getByTestId("dropdown_str_model_name").nth(i).click();
    await page.getByRole("option").first().click();
  }
};
