import type { Page } from "playwright/test";

export const loginLangflow = async (page: Page) => {
  await page.goto("/");
  await page.getByPlaceholder("Username").fill("langflow");
  await page.getByPlaceholder("Password").fill("langflow");
  await page.getByRole("button", { name: "Sign In" }).click();
};
