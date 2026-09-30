import type { Page } from "@playwright/test";

import { TEXTS } from "../utils/constants/texts";

export async function submitLoginAndRequireSuccess(page: Page): Promise<void> {
  const [response] = await Promise.all([
    page.waitForResponse((candidate) => {
      const path = new URL(candidate.url()).pathname;
      return (
        candidate.request().method() === "POST" && path === "/api/v1/login"
      );
    }),
    page.getByRole("button", { name: TEXTS.signIn }).click(),
  ]);
  if (!response.ok()) {
    throw new Error(`Login failed with HTTP ${response.status()}`);
  }
}

export const loginLangflow = async (page: Page) => {
  await page.goto("/");
  await page
    .getByPlaceholder(TEXTS.placeholderUsername)
    .fill(TEXTS.authDefaultCredential);
  await page
    .getByPlaceholder(TEXTS.placeholderPassword)
    .fill(TEXTS.authDefaultPassword);
  await submitLoginAndRequireSuccess(page);
};
