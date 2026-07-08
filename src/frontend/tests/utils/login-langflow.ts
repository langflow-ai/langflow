import type { Page } from "@playwright/test";

import { TEXTS } from "../utils/constants/texts";
export const loginLangflow = async (page: Page) => {
  await page.goto("/");
  await page
    .getByPlaceholder(TEXTS.placeholderUsername)
    .fill(TEXTS.authDefaultCredential);
  await page
    .getByPlaceholder(TEXTS.placeholderPassword)
    .fill(TEXTS.authDefaultPassword);
  await page.getByRole("button", { name: TEXTS.signIn }).click();
};
