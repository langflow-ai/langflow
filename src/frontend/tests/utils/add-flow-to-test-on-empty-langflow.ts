import type { Page } from "playwright/test";

export const addFlowToTestOnEmptyLangflow = async (page: Page) => {
  await page.getByTestId("new_project_btn_empty_page").click();
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.getByTestId("icon-ChevronLeft").click();
};
