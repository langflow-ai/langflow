import { Page } from "playwright/test";

export const selectGptModel = async (page: Page) => {
  const gptModelDropdownCount = await page
    .getByTestId("dropdown_str_model_name")
    .count();

  if (gptModelDropdownCount > 0) {
    await page.getByTestId("dropdown_str_model_name").nth(0).click();
    await page.getByTestId("gpt-4o-1-option").click();
  }
};
